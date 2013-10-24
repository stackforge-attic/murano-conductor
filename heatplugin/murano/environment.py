# vim: tabstop=4 shiftwidth=4 softtabstop=4

#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import json
import eventlet
from heat.openstack.common import log as logging
from heat.engine import resource
from muranoclient.v1.client import Client
from muranoclient.common.exceptions import HTTPNotFound
logger = logging.getLogger(__name__)


class MuranoEnvironment(resource.Resource):
    properties_schema = {
        'Body': {'Type': 'Map', 'Required': True},
        'MuranoApiEndpoint': {'Type': 'String'}
    }
    update_allowed_keys = ('Metadata', 'Properties')
    update_allowed_properties = ('Definition', 'MuranoApiEndpoint')
    attributes_schema = {}

    def __init__(self, name, json_snippet, stack):
        super(MuranoEnvironment, self).__init__(name, json_snippet, stack)

    def handle_create(self):
        self._update_environment()

    def handle_delete(self):
        client = self._muranoclient()
        environment_id = self._find_environment(client)
        if environment_id:
            client.environments.delete(environment_id)
            try:
                self._wait_deployed(client, environment_id)
            except HTTPNotFound:
                pass

    def _find_environment(self, client):
        environments = client.environments.list()
        for environment in environments:
            if environment.name == self.name:
                return environment.id
        return None

    def _update_environment(self):
        client = self._muranoclient()
        environment_id = self._find_environment(client)
        if not environment_id:
            environment_id = client.environments.create(self.name).id

        session_id = client.sessions.configure(environment_id).id
        environment = self.properties.get('Body')
        client.services.post(environment_id,
                             path='/',
                             data=environment.get('services', []),
                             session_id=session_id)
        client.sessions.deploy(environment_id, session_id)
        self._wait_deployed(client, environment_id)

    def _wait_deployed(self, client, environment_id):
        i = 0
        delay = 2
        while True:
            environment = client.environments.get(environment_id)
            if environment.status == 'pending' and i > 5 * 60:
                raise EnvironmentError(
                    "Environment deployment hasn't started")
            elif environment.status == 'deploying' and i > 65 * 60:
                raise EnvironmentError(
                    "Environment deployment takes too long")
            elif environment.status == 'ready':
                break
            eventlet.sleep(delay)
            i += delay

    def _muranoclient(self):
        endpoint = self._get_endpoint()
        token = self.stack.clients.auth_token
        return Client(endpoint=endpoint, token=token)

    def _get_endpoint(self):
        #prefer location specified in settings for dev purposes
        endpoint = self.properties.get('MuranoApiEndpoint')
        if not endpoint:
            endpoint = self.stack.clients.url_for(service_type='murano')
        return endpoint


def resource_mapping():
    return {
        'Murano::Environment': MuranoEnvironment
    }
