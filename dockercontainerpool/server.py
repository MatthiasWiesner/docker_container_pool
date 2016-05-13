#! /usr/bin/env python
import sys
import json
import click
import logging
import traceback
import docker.errors

from flask import Flask, request, current_app

from docker_container_pool import DockerContainerPool


__doc__ = '''
This module helps to maintain your docker container.
'''

app = Flask(__name__)
handler = logging.StreamHandler(stream=sys.stdout)
handler.setLevel(logging.DEBUG)
app.logger.addHandler(handler)


@click.command()
@click.option('--host', '-h', default='0.0.0.0')
@click.option('--port', '-p', default=5000)
@click.option('--verbose', '-v', is_flag=True)
@click.option('--dockerurl', '-u', default='unix://var/run/docker.sock')
def cli(host, port, verbose, dockerurl):
    with app.app_context():
        current_app.pool = DockerContainerPool(dockerurl)
    app.config['VERBOSE'] = verbose
    app.run(host=host, port=port)


@app.route("/container_group/<string:group_identifier>", methods=['POST'])
def add_container_group(group_identifier):
    '''  # nopep8
    The request body must be like this structure:
    ```json
    {
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
    current_app.pool.add_container_group(group_identifier, **parsed_json)
    return '', 200, {'ContentType': 'application/json'}


@app.route("/container_group/<string:group_identifier>", methods=['GET'])
def get_container_group(group_identifier):
    container_group = current_app.pool.get_container_group(group_identifier)
    return json.dumps(container_group.to_dict()), 200, {
        'ContentType': 'application/json'}


@app.route("/container_group/<string:group_identifier>", methods=['PUT'])
def update_container_group(group_identifier):
    parsed_json = request.get_json()
    container_group = current_app.pool.get_container_group(group_identifier)
    container_group.min_count = parsed_json.get(
        'min_count', container_group.min_count)
    container_group.max_count = parsed_json.get(
        'max_count', container_group.max_count)
    container_group.specs = parsed_json.get('specs', container_group.specs)
    return '', 200, {'ContentType': 'application/json'}


@app.route("/container_group/<string:group_identifier>/container", methods=['GET'])  # nopep8
def get_container_list(group_identifier):
    container_group = current_app.pool.get_container_group(group_identifier)
    container_list = container_group.get_container_list()
    return json.dumps(container_list), 200, {'ContentType': 'application/json'}


@app.route("/container_group/<string:group_identifier>/container/<string:container_identifier>", methods=['GET'])  # nopep8
def get_container(group_identifier, container_identifier):
    container_group = current_app.pool.get_container_group(group_identifier)
    container = container_group.get_container(container_identifier)
    return json.dumps(container), 200, {'ContentType': 'application/json'}


@app.route("/container_group/<string:group_identifier>/container", methods=['POST'])  # nopep8
def create_container(group_identifier):
    '''  # nopep8
    The request body must be like this structure:
    ```json
    {
      "start": true,
      "specs": {
                "command": ""
      }
    }
    ```
    '''
    parsed_json = request.get_json()
    container_group = current_app.pool.get_container_group(group_identifier)
    container = container_group.create_container(**parsed_json)
    return json.dumps(container), 200, {'ContentType': 'application/json'}


@app.route("/container_group/<string:group_identifier>/container/<string:container_identifier>/start", methods=['POST'])  # nopep8
def start_container(group_identifier, container_identifier):
    container_group = current_app.pool.get_container_group(group_identifier)
    container = container_group.start_container(container_identifier)
    return json.dumps(container), 200, {'ContentType': 'application/json'}


@app.route("/container_group/<string:group_identifier>/container/<string:container_identifier>/stop", methods=['POST'])  # nopep8
def stop_container(group_identifier, container_identifier):
    container_group = current_app.pool.get_container_group(group_identifier)
    container = container_group.stop_container(container_identifier)
    return json.dumps(container), 200, {'ContentType': 'application/json'}


@app.route("/container_group/<string:group_identifier>/container/<string:container_identifier>/exec", methods=['POST'])  # nopep8
def exec_command_container(group_identifier, container_identifier):
    '''  # nopep8
    The request body must be like this structure:
    ```json
    {
      "command": ""
    }
    ```
    '''
    parsed_json = request.get_json()
    container_group = current_app.pool.get_container_group(group_identifier)
    result = container_group.exec_command_container(
        container_identifier, parsed_json.get("command"))
    return json.dumps(result), 200, {'ContentType': 'application/json'}


@app.route("/container_group/<string:group_identifier>/container/<string:container_identifier>", methods=['DELETE'])  # nopep8
def remove_container(group_identifier, container_identifier):
    container_group = current_app.pool.get_container_group(group_identifier)
    container_group.remove_container(container_identifier)
    return '', 200, {'ContentType': 'application/json'}


@app.errorhandler(Exception)
def unhandled_exception(error):
    status = 500 if not hasattr(error, 'status_code') else error.status_code
    message = str(error)

    if isinstance(error, docker.errors.APIError):
        parts = str(error).split(":")
        status = int(parts[0].split()[0])
        message = parts[1].strip()

    response = dict(
        message=message,
        error_type=error.__class__.__name__)
    if app.config.get('VERBOSE', False):
        response['traceback'] = traceback.format_exc()
    return json.dumps(response), status, {
        'ContentType': 'application/json'}


if __name__ == '__main__':
    cli()
