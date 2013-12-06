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
import math
import muranoconductor.config
from keystoneclient.v2_0 import client as ksclient
import netaddr
from netaddr.strategy import ipv4
from neutronclient.v2_0 import client as client
from muranoconductor.commands.command import CommandBase


class NeutronExecutor(CommandBase):
    def __init__(self, tenant_id, token):
        keystone_settings = muranoconductor.config.CONF.keystone
        neutron_settings = muranoconductor.config.CONF.neutron

        self.env_count = muranoconductor.config.CONF.max_environments
        self.host_count = muranoconductor.config.CONF.max_hosts
        self.address = muranoconductor.config.CONF.env_ip_template

        self.cidr_waiting_per_router = {}
        self.cidr_waiting_per_network = {}
        self.router_requests = []
        self.network_requests = []
        self.tenant_id = tenant_id

        keystone_client = ksclient.Client(
            endpoint=keystone_settings.auth_url,
            cacert=keystone_settings.ca_file or None,
            cert=keystone_settings.cert_file or None,
            key=keystone_settings.key_file or None,
            insecure=keystone_settings.insecure)

        if not keystone_client.authenticate(
                auth_url=keystone_settings.auth_url,
                tenant_id=tenant_id,
                token=token):
            raise client.exceptions.Unauthorized()

        neutron_url = keystone_client.service_catalog.url_for(
            service_type='network',
            endpoint_type=neutron_settings.endpoint_type)
        self.neutron = client.Client(endpoint_url=neutron_url,
                                     token=token,
                                     ca_cert=neutron_settings.ca_cert or None,
                                     insecure=neutron_settings.insecure)

        self.command_map = {
            "get_new_subnet": self._schedule_get_new_subnet,
            "get_existing_subnet": self._schedule_get_existing_subnet,
            "get_router": self._schedule_get_router,
            "get_network": self._schedule_get_network
        }

    def execute(self, command, callback, **kwargs):
        if command in self.command_map:
            self.command_map[command](callback, **kwargs)

    def has_pending_commands(self):
        return len(self.cidr_waiting_per_router) + \
               len(self.cidr_waiting_per_network) + \
               len(self.router_requests) + len(self.network_requests) > 0

    def execute_pending(self):
        r1 = self._execute_pending_new_cidr_requests()
        r2 = self._execute_pending_net_requests()
        r3 = self._execute_pending_router_requests()
        r4 = self._execute_pending_existing_cidr_requests()
        return r1 or r2 or r3 or r4

    def _execute_pending_new_cidr_requests(self):
        if not len(self.cidr_waiting_per_router):
            return False
        for router, callbacks in self.cidr_waiting_per_router.items():
            results = self._get_subnet(router, len(callbacks))
            for callback, result in zip(callbacks, results):
                callback(result)
        self.cidr_waiting_per_router = {}
        return True

    def _execute_pending_existing_cidr_requests(self):
        if not len(self.cidr_waiting_per_network):
            return False
        for network, callbacks in self.cidr_waiting_per_network.items():
            result = self._get_existing_subnet(network)
            for callback in callbacks:
                callback(result)
        self.cidr_waiting_per_network = {}
        return True

    def _execute_pending_router_requests(self):
        if not len(self.router_requests):
            return False

        routers = self.neutron.list_routers(tenant_id=self.tenant_id). \
            get("routers")
        if not len(routers):
            routerId = None
        else:
            routerId = routers[0]["id"]

        if len(routers) > 1:
            for router in routers:
                if "murano" in router["name"].lower():
                    routerId = router["id"]
                    break
        for callback in self.router_requests:
            callback(routerId)
        self.router_requests = []
        return True

    def _execute_pending_net_requests(self):
        if not len(self.network_requests):
            return False

        nets = self.neutron.list_networks()["networks"]
        if not len(nets):
            netId = None
        else:
            netId = nets[0]["id"]
        if len(nets) > 1:
            murano_id = None
            ext_id = None
            shared_id = None
            for net in nets:
                if "murano" in net.get("name").lower():
                    murano_id = net["id"]
                    break
                if net.get("router:external") and not ext_id:
                    ext_id = net["id"]
                if net.get("shared") and not shared_id:
                    shared_id = net["id"]
            if murano_id:
                netId = murano_id
            elif ext_id:
                netId = ext_id
            elif shared_id:
                netId = shared_id
        for callback in self.network_requests:
            callback(netId)
        self.network_requests = []
        return True

    def _get_subnet(self, routerId, count):
        if routerId == "*":
            routerId = None
        if routerId:
            taken_cidrs = self._get_taken_cidrs_by_router(routerId)
        else:
            taken_cidrs = self._get_all_taken_cidrs()
        results = []
        for i in range(0, count):
            res = self._generate_cidr(taken_cidrs)
            results.append(res)
            taken_cidrs.append(res)
        return results

    def _get_existing_subnet(self, network_id):
        subnets = self.neutron.list_subnets(network_id=network_id)['subnets']
        if not subnets:
            return None
        else:
            return subnets[0]['cidr']

    def _get_taken_cidrs_by_router(self, routerId):
        ports = self.neutron.list_ports(device_id=routerId)["ports"]
        subnet_ids = []
        for port in ports:
            for fixed_ip in port["fixed_ips"]:
                subnet_ids.append(fixed_ip["subnet_id"])

        all_subnets = self.neutron.list_subnets()["subnets"]
        filtered_cidrs = [subnet["cidr"] for subnet in all_subnets if
                          subnet["id"] in subnet_ids]

        return filtered_cidrs

    def _get_all_taken_cidrs(self):
        return [subnet["cidr"] for subnet in
                self.neutron.list_subnets()["subnets"]]

    def _generate_cidr(self, taken_cidrs):
        bits_for_envs = int(math.ceil(math.log(self.env_count, 2)))
        bits_for_hosts = int(math.ceil(math.log(self.host_count, 2)))
        width = ipv4.width
        mask_width = width - bits_for_hosts - bits_for_envs
        net = netaddr.IPNetwork(self.address + "/" + str(mask_width))
        for subnet in net.subnet(width - bits_for_hosts):
            if str(subnet) in taken_cidrs:
                continue
            return str(subnet)
        return None

    def _schedule_get_new_subnet(self, callback, **kwargs):
        routerId = kwargs.get("routerId")
        if not routerId:
            routerId = "*"
        if routerId in self.cidr_waiting_per_router:
            self.cidr_waiting_per_router[routerId].append(callback)
        else:
            self.cidr_waiting_per_router[routerId] = [callback]

    def _schedule_get_existing_subnet(self, callback, **kwargs):
        existing_network = kwargs.get("existingNetwork")

        if existing_network in self.cidr_waiting_per_network:
            self.cidr_waiting_per_network[existing_network].append(callback)
        else:
            self.cidr_waiting_per_network[existing_network] = [callback]

    def _schedule_get_router(self, callback, **kwargs):
        self.router_requests.append(callback)

    def _schedule_get_network(self, callback, **kwargs):
        self.network_requests.append(callback)
