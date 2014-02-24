#    Copyright (c) 2013 Mirantis, Inc.
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

from oslo import messaging
from oslo.messaging.rpc.client import RPCClient
from oslo.messaging.target import Target

from muranoconductor import config

TRANSPORT = None


class ApiClient(object):
    def __init__(self, transport):
        target = Target('murano', 'results')
        self._client = RPCClient(transport, target, timeout=15)

    def process_result(self, result):
        return self._client.call({}, 'process_result', result=result)


def api():
    global TRANSPORT
    if TRANSPORT is None:
        TRANSPORT = messaging.get_transport(config.CONF)

    return ApiClient(TRANSPORT)
