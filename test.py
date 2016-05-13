import json
import unittest
from docker.errors import APIError
from mock import Mock, patch, call
from flask import current_app
from dockercontainerpool.server import app
from dockercontainerpool.docker_container_pool import DockerContainerPool


class DockerContainerPoolTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pass

    @classmethod
    def tearDownClass(clss):
        pass

    @patch('dockercontainerpool.docker_container_pool.docker.Client')
    def setUp(self, docker_client):
        self.docker_client_mock = Mock()
        docker_client.return_value = self.docker_client_mock

        with app.app_context() as app_context:
            current_app.pool = DockerContainerPool(
                'unix://path/to/docker.sock')

        app.config['VERBOSE'] = True

        self.client = app.test_client()
        self.client.testing = True

    def tearDown(self):
        pass

    def test_add_container_group(self):
        headers = {"Content-Type": "application/json"}
        result = self.client.post(
            '/container_group/redis',
            headers=headers, data=json.dumps({
                "min_count": 1,
                "max_count": 5,
                "specs": {
                    "image": "redis"
                }
            }))
        self.assertEqual(200, result.status_code)

        headers = {"Content-Type": "application/json"}
        result = self.client.post(
            '/container_group/redis',
            headers=headers, data=json.dumps({
                "min_count": 1,
                "max_count": 5,
                "specs": {
                    "image": "redis"
                }
            }))
        self.assertEqual("DockerContainerPoolGroupAlreadyDeclared", json.loads(
            result.data).get("error_type"))
        self.assertEqual(500, result.status_code)

    def test_update_container_group(self):
        # update not existing container group
        container_group_conf = {
            "min_count": 1,
            "max_count": 5,
            "specs": {
                "image": "redis"
            }
        }
        headers = {"Content-Type": "application/json"}
        result = self.client.put(
            '/container_group/redis',
            headers=headers, data=json.dumps(container_group_conf))
        self.assertEqual("DockerContainerPoolGroupNotFound", json.loads(
            result.data).get("error_type"))
        self.assertEqual(404, result.status_code)

        # set initial container group
        self._set_container_group()

        headers = {"Content-Type": "application/json"}
        result = self.client.put(
            '/container_group/redis',
            headers=headers, data=json.dumps(container_group_conf))
        self.assertEqual(200, result.status_code)

        result = self.client.get('/container_group/redis')
        self.assertEqual(container_group_conf, json.loads(result.data))

        # update container group
        container_group_conf = {
            "min_count": 10,
            "max_count": 50,
            "specs": {
                "image": "other-redis"
            }
        }

        headers = {"Content-Type": "application/json"}
        result = self.client.put(
            '/container_group/redis',
            headers=headers, data=json.dumps(container_group_conf))
        self.assertEqual(200, result.status_code)

        result = self.client.get('/container_group/redis')
        self.assertEqual(container_group_conf, json.loads(result.data))

    @patch('dockercontainerpool.docker_container_group.uuid')
    def test_create_container(self, uuid):
        uuid.uuid4.return_value = 'aaaa-aaaa-aaaa-aaaa'

        self._set_container_group(max_count=1)

        container_id = 'meinecontainerid'
        mycontainer = self._get_container_response(container_id)

        self.docker_client_mock.containers.side_effect = [
            [],
            [mycontainer],
            [mycontainer],
        ]
        self.docker_client_mock.create_container.return_value = mycontainer

        headers = {"Content-Type": "application/json"}
        result = self.client.post(
            '/container_group/redis/container',
            headers=headers, data=json.dumps({
                "start": True
                }))
        self.assertEqual(200, result.status_code)
        self.assertEqual(mycontainer, json.loads(result.data))
        self.assertEqual(
            call(u'redis', name='redis--aaaa-aaaa-aaaa-aaaa'),
            self.docker_client_mock.create_container.call_args)

        headers = {"Content-Type": "application/json"}
        result = self.client.post(
            '/container_group/redis/container',
            headers=headers, data=json.dumps({
                "start": True
                }))
        self.assertEqual("DockerContainerGroupMaxCountReached", json.loads(
            result.data).get("error_type"))
        self.assertEqual(500, result.status_code)

    def test_start_container(self):
        self._set_container_group(max_count=1)

        container_id = 'meinecontainerid'
        mycontainer = self._get_container_response(container_id, 'running')
        self.docker_client_mock.containers.return_value = [mycontainer]

        headers = {"Content-Type": "application/json"}
        result = self.client.post(
            '/container_group/redis/container/{0}/start'.format(container_id),
            headers=headers)
        self.assertEqual(200, result.status_code)
        self.assertEqual(mycontainer, json.loads(result.data))
        self.assertEquals(
            call(all=True, filters={'id': u'meinecontainerid'}),
            self.docker_client_mock.containers.call_args)
        self.assertEquals(
            call(u'meinecontainerid'),
            self.docker_client_mock.start.call_args)

    def test_stop_container(self):
        self._set_container_group(max_count=1)

        container_id = 'meinecontainerid'
        mycontainer = self._get_container_response(container_id, 'exited')

        self.docker_client_mock.containers.return_value = [mycontainer]

        headers = {"Content-Type": "application/json"}
        result = self.client.post(
            '/container_group/redis/container/{0}/stop'.format(container_id),
            headers=headers)
        self.assertEqual(200, result.status_code)
        self.assertEqual(mycontainer, json.loads(result.data))
        self.assertEquals(
            call(all=True, filters={'id': u'meinecontainerid'}),
            self.docker_client_mock.containers.call_args)
        self.assertEquals(
            call(u'meinecontainerid'),
            self.docker_client_mock.stop.call_args)

    def test_exec_command_container(self):
        self._set_container_group(max_count=1)

        container_id = 'meinecontainerid'
        mycontainer = self._get_container_response(container_id, 'running')

        answer = "total 4\n-rw-r--r-- 1 redis redis 18 May 10 13:08 dump.rdb\n"

        self.docker_client_mock.exec_create.return_value = 'exec_id'
        self.docker_client_mock.exec_start.return_value = answer

        headers = {"Content-Type": "application/json"}
        result = self.client.post(
            '/container_group/redis/container/{0}/exec'.format(container_id),
            headers=headers, data=json.dumps(dict(command="ls -l")))
        self.assertEqual(200, result.status_code)
        self.assertEqual(answer, json.loads(result.data))
        self.assertEqual(
            call(cmd=u'ls -l', container=u'meinecontainerid'),
            self.docker_client_mock.exec_create.call_args)
        self.assertEqual(
            call(exec_id=u'exec_id'),
            self.docker_client_mock.exec_start.call_args)

    def test_remove_container(self):
        self._set_container_group(max_count=1)

        self.docker_client_mock.kill.side_effect = APIError(
            Mock(), Mock(), "explanation")

        container_id = 'meinecontainerid'
        headers = {"Content-Type": "application/json"}
        result = self.client.delete(
            '/container_group/redis/container/{0}'.format(container_id),
            headers=headers)

        self.assertEqual(
            call(u'meinecontainerid'),
            self.docker_client_mock.kill.call_args)
        self.assertEqual(
            call(u'meinecontainerid'),
            self.docker_client_mock.wait.call_args)
        self.assertEqual(
            call(u'meinecontainerid'),
            self.docker_client_mock.remove_container.call_args)

    def test_remove_multiple_conatainer(self):
        pass

    def _set_container_group(
            self,
            group_identifier='redis',
            min_count=1,
            max_count=5,
            image='redis'):

        headers = {"Content-Type": "application/json"}
        return self.client.post(
            '/container_group/' + group_identifier,
            headers=headers, data=json.dumps(
                dict(
                    min_count=min_count,
                    max_count=max_count,
                    specs=dict(image=image)
                )))

    def _get_container_response(self, container_id, state='created'):
        # return a docker like container structure
        # name differs from the created one
        return {
                u'Status': u'Created',
                u'Created': 1462873363,
                u'Image': u'redis',
                u'Labels': {},
                u'NetworkSettings': {
                    u'Networks': {
                        u'bridge': {
                            u'NetworkID': u'',
                            u'MacAddress': u'',
                            u'GlobalIPv6PrefixLen': 0,
                            u'Links': None,
                            u'GlobalIPv6Address': u'',
                            u'IPv6Gateway': u'',
                            u'IPAMConfig': None,
                            u'EndpointID': u'',
                            u'IPPrefixLen': 0,
                            u'IPAddress': u'',
                            u'Gateway': u'',
                            u'Aliases': None}}},
                u'HostConfig': {},
                u'ImageID': u'sha256:0f0e96f1f267825691dff138a7f0d392aa4de3fc6eaf1f830e1b7c18cbd556b8',  # nopep8
                u'State': state,
                u'Command': u'docker-entrypoint.sh redis-server',
                u'Names': [u'/redis--aaaa-aaaa-aaaa-aaaa'],
                u'Mounts': [{
                    u'RW': True,
                    u'Name': u'bd37a599ae8ce232e4778614610da70f49fa8f7d38e29d2b0379eea8b656844d',  # nopep8
                    u'Propagation': u'',
                    u'Destination': u'/data',
                    u'Driver': u'local',
                    u'Source': u'/var/lib/docker/volumes/bd37a599ae8ce232e4778614610da70f49fa8f7d38e29d2b0379eea8b656844d/_data',  # nopep8
                    u'Mode': u''}],
                u'Id': container_id,
                u'Ports': []
        }


if __name__ == '__main__':
    unittest.main()
