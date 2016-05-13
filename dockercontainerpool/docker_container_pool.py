import docker

from errors import (
    DockerContainerPoolException,
    DockerContainerPoolGroupNotFound,
    DockerContainerPoolGroupAlreadyDeclared
)
from docker_container_group import DockerContainerGroup


class DockerContainerPool(object):
    client = None
    container_group_list = None

    def __init__(self, base_url):
        self.container_group_list = {}
        try:
            self.client = docker.Client(base_url=base_url)
        except Exception:
            raise DockerContainerPoolException(message=str(Exception))

    def get_container_group(self, group_identifier):
        if group_identifier not in self.container_group_list:
            raise DockerContainerPoolGroupNotFound()
        return self.container_group_list[group_identifier]

    def add_container_group(self, group_identifier, *args, **kwargs):
        if group_identifier in self.container_group_list:
            raise DockerContainerPoolGroupAlreadyDeclared()
        container_group = DockerContainerGroup(
            group_identifier, self.client, *args, **kwargs)
        self.container_group_list[group_identifier] = container_group

    def create_container(self, group_identifier, start=False):
        container_group = self.get_container_group()
        container_group.create_container(start=start)

    def remove_container(
            self, group_identifier, count, force_used_container=False):
        container_group = self.get_container_group()
        container_group.remove_container(
            count, force_used_container=force_used_container)
