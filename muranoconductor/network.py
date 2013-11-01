# Copyright (c) 2013 Mirantis Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from muranoconductor import xml_code_engine
import muranoconductor.config

from openstack.common import log as logging

log = logging.getLogger(__name__)


def get_available_subnet(engine, context, body, routerId=None, result=None):
    command_dispatcher = context['/commandDispatcher']

    def callback(result_value):
        if result is not None:
            context[result] = {"cidr": result_value}

        success_handler = body.find('success')
        if success_handler is not None:
            engine.evaluate_content(success_handler, context)

    command_dispatcher.execute(
        name="net",
        command="get_subnet",
        routerId=routerId,
        callback=callback)


def get_default_router(engine, context, body, result=None):
    command_dispatcher = context['/commandDispatcher']

    def callback(result_value):
        if result is not None:
            context[result] = {"routerId": result_value}

        success_handler = body.find('success')
        if success_handler is not None:
            engine.evaluate_content(success_handler, context)

    command_dispatcher.execute(
        name="net",
        command="get_router",
        callback=callback)


def get_default_network(engine, context, body, result=None):
    command_dispatcher = context['/commandDispatcher']

    def callback(result_value):
        if result is not None:
            context[result] = {"networkId": result_value}

        success_handler = body.find('success')
        if success_handler is not None:
            engine.evaluate_content(success_handler, context)

    command_dispatcher.execute(
        name="net",
        command="get_network",
        callback=callback)


def get_network_topology(engine, context, body, result=None):
    if muranoconductor.config.CONF.flat_by_default:
        return "flat"
    else:
        return "routed"


xml_code_engine.XmlCodeEngine.register_function(
    get_available_subnet, "get-cidr")

xml_code_engine.XmlCodeEngine.register_function(
    get_default_router, "get-default-router-id")

xml_code_engine.XmlCodeEngine.register_function(
    get_default_network, "get-default-network-id")

xml_code_engine.XmlCodeEngine.register_function(
    get_default_router, "get-default-router-id")

xml_code_engine.XmlCodeEngine.register_function(
    get_network_topology, "get-net-topology")