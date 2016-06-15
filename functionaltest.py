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

    def setUp(self):
        with app.app_context() as app_context:
            current_app.pool = DockerContainerPool(
                'unix://var/run/docker.sock')

        app.config['VERBOSE'] = True

        self.client = app.test_client()
        self.client.testing = True

    def tearDown(self):
        self.client.delete('/container_group/redis')

    def test_set_running_container_increase(self):
        self._set_container_group()

        headers = {"Content-Type": "application/json"}
        result = self.client.post(
            '/container_group/redis/set_running_container',
            headers=headers, data=json.dumps(
                dict(count=3)))
        parsed_json = json.loads(
            self.client.get('/container_group/redis/container').data)
        self.assertEqual(3, len(parsed_json))
        for container in parsed_json:
            self.assertEqual(u'running', container['State'])

    def test_set_running_container_increase_with_created_container(self):
        self._set_container_group()

        headers = {"Content-Type": "application/json"}

        for _ in range(3):
            self._start_container(start=False)

        parsed_json = json.loads(
            self.client.get('/container_group/redis/container').data)
        self.assertEqual(3, len(parsed_json))

        self.client.post(
            '/container_group/redis/set_running_container',
            headers=headers, data=json.dumps(
                dict(count=4)))

        parsed_json = json.loads(
            self.client.get('/container_group/redis/container').data)
        self.assertEqual(4, len(parsed_json))

        count_running = 0
        count_available = 0
        for container in parsed_json:
            if container['State'] == u'running':
                count_running += 1
            if container['State'] == u'created':
                count_available += 1
        self.assertEqual(4, count_running)
        self.assertEqual(0, count_available)

    def test_set_running_container_increase_with_exited_container(self):
        self._set_container_group()

        headers = {"Content-Type": "application/json"}

        for _ in range(3):
            container = self._start_container(start=True)
            self._stop_container(container['Id'])

        self.client.post(
            '/container_group/redis/set_running_container',
            headers=headers, data=json.dumps(
                dict(count=2)))

        parsed_json = json.loads(
            self.client.get('/container_group/redis/container').data)
        self.assertEqual(3, len(parsed_json))

        count_running = 0
        count_available = 0
        for container in parsed_json:
            if container['State'] == u'running':
                count_running += 1
            if container['State'] == u'exited':
                count_available += 1
        self.assertEqual(2, count_running)
        self.assertEqual(1, count_available)

    def test_set_running_container_decrease(self):
        self._set_container_group()
        headers = {"Content-Type": "application/json"}

        for _ in range(3):
            self._start_container(start=True)

        parsed_json = json.loads(
            self.client.get('/container_group/redis/container').data)
        self.assertEqual(3, len(parsed_json))

        self.client.post(
            '/container_group/redis/set_running_container',
            headers=headers, data=json.dumps(
                dict(count=1)))

        parsed_json = json.loads(
            self.client.get('/container_group/redis/container').data)

        count_running = 0
        count_available = 0
        for container in parsed_json:
            if container['State'] == u'running':
                count_running += 1
            if container['State'] == u'exited':
                count_available += 1
        self.assertEqual(1, count_running)
        self.assertEqual(2, count_available)

    def test_set_available_container_increase(self):
        self._set_container_group()

        headers = {"Content-Type": "application/json"}
        result = self.client.post(
            '/container_group/redis/set_available_container',
            headers=headers, data=json.dumps(
                dict(count=3)))
        parsed_json = json.loads(
            self.client.get('/container_group/redis/container').data)
        self.assertEqual(3, len(parsed_json))
        for container in parsed_json:
            self.assertEqual(u'created', container['State'])

    def test_set_available_container_decrease(self):
        self._set_container_group()

        for _ in range(3):
            container = self._start_container(start=False)
        self._stop_container(container['Id'])
        self._start_container(start=True)

        headers = {"Content-Type": "application/json"}
        self.client.post(
            '/container_group/redis/set_available_container',
            headers=headers, data=json.dumps(
                dict(count=1)))

        parsed_json = json.loads(
            self.client.get('/container_group/redis/container').data)
        count_running = 0
        count_available = 0
        for container in parsed_json:
            if container['State'] == u'running':
                count_running += 1
            if container['State'] in [u'exited', 'created']:
                count_available += 1
        self.assertEqual(1, count_running)
        self.assertEqual(1, count_available)

    def _set_container_group(
            self,
            group_identifier='redis',
            image='redis'):

        headers = {"Content-Type": "application/json"}
        return self.client.post(
            '/container_group/' + group_identifier,
            headers=headers, data=json.dumps(
                dict(
                    specs=dict(image=image)
                )))

    def _start_container(self, start=False):
        headers = {"Content-Type": "application/json"}
        return json.loads(self.client.post(
            '/container_group/redis/container',
            headers=headers, data=json.dumps(
                dict(start=start))).data)

    def _stop_container(self, container_id):
        headers = {"Content-Type": "application/json"}
        self.client.post(
            '/container_group/redis/%s/stop' % container_id,
            headers=headers, data=json.dumps(dict()))


if __name__ == '__main__':
    unittest.main()
