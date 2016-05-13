import sys
import uuid
import docker
import logging

from copy import deepcopy
from docker.errors import APIError

from errors import DockerContainerGroupMaxCountReached


__doc__ = '''
This module helps to maintain your docker container.
'''

logger = logging.getLogger(__name__)
handler = logging.StreamHandler(stream=sys.stdout)
handler.setLevel(logging.DEBUG)
logger.addHandler(handler)


class DockerContainerGroup(object):
    group_identifier = None
    client = None
    min_count = 0
    max_count = 0
    specs = {}

    container_list = []

    def __init__(
            self,
            group_identifier,
            client,
            min_count,
            max_count,
            specs,
            update_image=False):

        self.group_identifier = group_identifier
        self.client = client
        self.min_count = min_count
        self.max_count = max_count
        self.specs = specs

        if update_image:
            self.client.pull(specs['image'])

    def get_container_list(self, status=False):
        filters = dict(name='/{}--'.format(self.group_identifier))
        if status:
            filters['status'] = status

        return self.client.containers(all=True, filters=filters)

    def get_container(self, container_identifier):
        return self.client.containers(all=True, filters=dict(
            id=container_identifier))[0]

    def create_container(self, start=True, specs={}):
        # http://docker-py.readthedocs.io/en/latest/api/#create_container
        if len(self.get_container_list()) >= self.max_count:
            raise DockerContainerGroupMaxCountReached()

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

    def remove_container(self, container_identifier):
        self._kill_remove_container(container_identifier)

    def remove_multiple_container(self, count, force_used_container=False):
        available_container = self.get_container_list(
            status=['created', 'exited'])

        count_available = len(available_container)
        count_rm_from_avail = min(count_available, count)

        for i, c in enumerate(available_container[0:count_rm_from_avail]):
            self._kill_remove_container(c['container'])
            del self.container_list[i]

        # are still some containers left to be removed?
        if count > count_rm_from_avail and force_used_container:
            used_container = self.get_container_list(
                status='running')

            count_used = len(used_container)
            count_rm_from_used = min(
                count_used, count - count_rm_from_avail)

            for i, c in enumerate(used_container[0:count_rm_from_used]):
                self._kill_remove_container(c['container'])
                del self.container_list[i]

    def _kill_remove_container(self, container_id):
        # if we run into problems, see here: http://blog.bordage.pro/avoid-docker-py/  # nopep8
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
        return dict(min_count=self.min_count,
                    max_count=self.max_count,
                    specs=self.specs)
