
class DockerContainerPoolException(Exception):
    status_code = 500


class DockerContainerPoolGroupAlreadyDeclared(DockerContainerPoolException):
    pass


class DockerContainerPoolGroupNotFound(DockerContainerPoolException):
    status_code = 404


class DockerContainerGroupException(DockerContainerPoolException):
    pass


class DockerContainerGroupMaxCountReached(DockerContainerGroupException):
    pass
