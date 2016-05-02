#! /usr/bin/env python
import sys
import click
import docker
import logging
from copy import deepcopy
from flask import Flask, request, jsonify


__doc__ = '''
This module helps to maintain your docker container.
'''

app = Flask(__name__)
h1 = logging.StreamHandler(stream=sys.stdout)
h1.setLevel(logging.DEBUG)
app.logger.addHandler(h1)

# app.logger is only available in flask.app decorated funtions
logger = app.logger


class DockerContainerPoolException(Exception):
    pass


class DockerContainerPoolMaxCountException(Exception):
    pass


class DockerContainerPool(object):
    client = None
    container_group_list = {}

    def __init__(self, base_url):
        self.client = docker.Client(base_url=base_url)

    def get_container_group(self, group_identifier):
        return self.container_group_list[group_identifier]

    def add_container_group(
            self, group_identifier, min_count, max_count, specs):
        container_group = DockerContainerPoolGroup(
            group_identifier, self.client, min_count, max_count, specs)

        self.container_group_list[group_identifier] = container_group

    def create_container(self, group_identifier, start=False):
        container_group = self.container_group_list[group_identifier]
        container_group.create_container(start=start)

    def remove_container(
            self, group_identifier, count, force_used_container=False):
        container_group = self.container_group_list[group_identifier]
        container_group.remove_container(
            count, force_used_container=force_used_container)


class DockerContainerPoolGroup(object):
    group_identifier = None
    client = None
    min_count = 0
    max_count = 0
    specs = {}

    container_list = {}
    status = {
        'AVAILABLE': 0,
        'USED': 1
    }

    def __init__(self, group_identifier, client, min_count, max_count, specs):
        print group_identifier, client, min_count, max_count

        self.group_identifier = group_identifier
        self.client = client
        self.min_count = min_count
        self.max_count = max_count
        self.specs = specs

    def get_container_list(self, status=False):
        if not status:
            return self.container_list
        else:
            return {k: v for k, v in self.container_list.iteritems()
                    if v['status'] == status}

    def create_container(self, start=True):
        if len(self.container_list) >= self.max_count:
            raise DockerContainerPoolMaxCountException()

        specs = deepcopy(self.specs)
        image = specs.pop('image')
        try:
            container = self.client.create_container(image, **specs)
        except docker.errors.NotFound:
            self.client.pull(image)
            container = self.client.create_container(image, **specs)

        status = self.status['AVAILABLE']
        if start:
            self.client.start(container=container.get('Id'))
            status = self.status['USED']

        container_identifier = container.get('Id')
        self.container_list[container_identifier] = dict(
            container=container, status=status)

        print self.container_list
        return dict(
            container_identifier=container_identifier,
            container=dict(
                container=str(container),
                status=self.status.keys()[
                    self.status.values().index(status)]))

    def remove_container(self, container_identifier):
        container = self.container_list[container_identifier]['container']
        self._kill_remove_container(container)

    def remove_multiple_container(self, count, force_used_container=False):
        available_container = self.get_container_list(
            status=self.status['AVAILABLE'])

        count_available = len(available_container)
        count_rm_from_avail = min(count_available, count)

        for key in available_container.keys()[0:count_rm_from_avail]:
            container = self.container_list[key]['container']
            self._kill_remove_container(container)
            del self.container_list[key]

        # are still some containers left to be removed?
        if count > count_rm_from_avail and force_used_container:
            used_container = self.get_container_list(
                status=self.status['USED'])

            count_used = len(used_container)
            count_rm_from_used = min(
                count_used, count - count_rm_from_avail)

            for key in used_container.keys()[0:count_rm_from_used]:
                container = self.container_list[key]['container']
                self._kill_remove_container(container['container'])
                del self.container_list[key]

    def _kill_remove_container(self, container):
        # if we run into problems, see here: http://blog.bordage.pro/avoid-docker-py/  # nopep8
        try:
            self.client.kill(container)
        except docker.errors.APIError as e:
            logger.error(e)
            self.client.wait(container)
        try:
            self.client.remove_container(container)
        except APIError as e:
            logger.error(e)  # This should work anyway (and I don't understand why)  # nopep8


@click.command()
@click.option('--host', '-h', default='0.0.0.0')
@click.option('--port', '-p', default=5000)
@click.option('--debug', '-d', is_flag=True)
@click.option('--dockerurl', '-u', default='unix://var/run/docker.sock')
@click.pass_context
def cli(ctx, host, port, debug, dockerurl):
    ctx.obj = DockerContainerPool(dockerurl)
    app.run(host=host, port=port, debug=debug)


@app.route("/container_group", methods=['POST'])
@click.pass_context
def add_container_group(ctx):
    '''  # nopep8
    The request body must be like this structure:
    ```json
    {
      "group_identifier": "redis",
      "min_count": 1,
      "max_count": 5,
      "specs": {
                "image": "redis",
                "command": ""
      }
    }

    ```
    for more docker container options see: http://docker-py.readthedocs.io/en/latest/api/#create_container
    ATTENTION! Many options are deprecated
    '''
    parsed_json = request.get_json()
    ctx.obj.add_container_group(**parsed_json)
    return '', 200, {'ContentType': 'application/json'}


@app.route("/container_group/<string:group_identifier>", methods=['PUT'])
@click.pass_context
def update_container_group(ctx, group_identifier):
    parsed_json = request.get_json()
    container_group = ctx.obj.get_container_group(group_identifier)
    container_group.min_count = parsed_json.get(
        'min_count', container_group.min_count)
    container_group.max_count = parsed_json.get(
        'max_count', container_group.max_count)
    container_group.specs = parsed_json.get('specs', container_group.specs)
    return '', 200, {'ContentType': 'application/json'}


@app.route("/container_group/<string:group_identifier>", methods=['POST'])
@click.pass_context
def create_container(ctx, group_identifier):
    parsed_json = request.get_json()
    container_group = ctx.obj.get_container_group(group_identifier)
    container = container_group.create_container(**parsed_json)
    return jsonify(container), 200, {'ContentType': 'application/json'}


@app.route(
    "/container_group/<string:group_identifier>/<string:container_identifier>",
    methods=['DELETE'])
@click.pass_context
def remove_container(ctx, group_identifier, container_identifier):
    container_group = ctx.obj.get_container_group(group_identifier)
    container_group.remove_container(container_identifier)
    return '', 200, {'ContentType': 'application/json'}


if __name__ == '__main__':
    cli()
