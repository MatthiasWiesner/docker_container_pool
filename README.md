# docker_container_pool

A docker-wrapper tool to handle docker container groups. 
A docker container group is here a group of same docker containers, that share the same settings.
So, **this is not a docker swarm** (which is a cluster of docker hosts)

This tool provides a RESTlike interface to start, stop or delete containers.

Look at te unittests and functionaltests for detailed info...

## Create a docker container group

To create a docker container group do a POST request to:
`http://{{base_url}}/container_group/<string:group_identifier>/container`
with a json data structure like:
```json
{
  "start": true,
  "specs": {
            "command": ""
  }
}
```
whereby the specs are directly passed to the docker python binding (which passes the specs to the docker remote api as well).
For details see more at: https://docker-py.readthedocs.io/en/latest/api/#create_container

**But, be careful!** I often faced issues, due to an obsolete docker python binding API doc. You should also consult
the Docker Remote Api (latest version).
Currently: https://docs.docker.com/engine/reference/api/docker_remote_api_v1.23/#create-a-container