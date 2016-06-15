import sys
import uuid
import docker
import logging

from copy import deepcopy
from docker.errors import APIError


__doc__ = '''
This module helps to maintain your docker container group.
'''

logger = logging.getLogger(__name__)
handler = logging.StreamHandler(stream=sys.stdout)
handler.setLevel(logging.DEBUG)
logger.addHandler(handler)


class DockerContainerGroup(object):
    group_identifier = None
    client = None
    specs = {}

    def __init__(
            self,
            group_identifier,
            client,
            specs,
            update_image=False):

        self.group_identifier = group_identifier
        self.client = client
        self.specs = specs

        if update_image:
            self.client.pull(specs['image'])

    def get_container_list(self, status=False):
        filters = dict(name='/{}--'.format(self.group_identifier))
        if status:
            filters['status'] = status

        return self.client.containers(all=True, filters=filters)

    def get_available_container_list(self):
        return self.get_container_list(status=['created', 'exited'])

    def get_running_container_list(self):
        return self.get_container_list(status=['running'])

    def get_container(self, container_identifier):
        return self.client.containers(all=True, filters=dict(
            id=container_identifier))[0]

    def create_container(self, start=True, specs={}):
        # http://docker-py.readthedocs.io/en/latest/api/#create_container
        predefined_specs = deepcopy(self.specs)
        image = predefined_specs.pop('image')

        if specs:
            predefined_specs.update(specs)

        predefined_specs['name'] = '{}--{}'.format(
            self.group_identifier, str(uuid.uuid4()))

        container = self.client.create_container(image, **predefined_specs)
        if start:
            self.client.start(container.get('Id'))

        return self.get_container(container.get('Id'))

    def start_container(self, container_identifier):
        # http://docker-py.readthedocs.io/en/latest/api/#start
        self.client.start(container_identifier)
        return self.get_container(container_identifier)

    def stop_container(self, container_identifier):
        # http://docker-py.readthedocs.io/en/latest/api/#stop
        self.client.stop(container_identifier)
        return self.get_container(container_identifier)

    def exec_command_container(self, container_identifier, command):
        # http://docker-py.readthedocs.io/en/latest/api/#exec_create
        exec_id = self.client.exec_create(
            container=container_identifier,
            cmd=command)

        return self.client.exec_start(
            exec_id=exec_id)

    def remove_all_container(self):
        for container in self.get_container_list():
            self.remove_container(container.get('Id'))

    def set_running_container(self, count):
        running_container_list = self.get_running_container_list()
        count_running = len(running_container_list)
        count_to_start = count - count_running
        if count_to_start == 0:
            return

        # start available container and create new ones, if necessary
        if count_to_start > 0:
            available_containers = self.get_available_container_list()
            for i in range(min(count_to_start, len(available_containers))):
                c = available_containers[i]
                self.start_container(c.get('Id'))
                count_to_start -= 1

            for _ in range(count_to_start):
                self.create_container(start=True)
        else:
            for i in range(count_running - count):
                c = running_container_list[i]
                self.stop_container(c.get('Id'))

    def set_available_container(self, count):
        available_container_list = self.get_available_container_list()
        count_available = len(available_container_list)
        count_to_start = count - count_available
        if count_to_start == 0:
            return

        # start available container and create new ones, if necessary
        if count_to_start > 0:
            for _ in range(count_to_start):
                self.create_container(start=False)
        else:
            for i in range(count_available - count):
                c = available_container_list[i]
                self.remove_container(c.get('Id'))

    def remove_container(self, container_identifier):
        self._kill_remove_container(container_identifier)

    def _kill_remove_container(self, container_id):
        # if we run into problems, see here: http://blog.bordage.pro/avoid-docker-py/  # nopep8
        container = self.get_container(container_id)
        if container['State'] == 'running':
            try:
                self.client.kill(container_id)
            except APIError as e:
                logger.error(e)
                self.client.wait(container_id)

        try:
            self.client.remove_container(container_id)
        except APIError as e:
            logger.error(e)  # This should work anyway (and I don't understand why)  # nopep8

    def to_dict(self):
        return dict(specs=self.specs)
