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

import anyjson
import eventlet
import types

from muranoconductor.openstack.common import log as logging
import muranoconductor.helpers
from command import CommandBase
import muranoconductor.config
import heatclient.exc
from keystoneclient.v2_0 import client as ksclient
from heatclient import client as heat_client
from quantumclient.v2_0 import client as quantum_client

log = logging.getLogger(__name__)


class HeatExecutor(CommandBase):
    def __init__(self, stack, token, tenant_id, reporter):
        self._update_pending_list = []
        self._delete_pending_list = []
        self._stack = stack
        self._reporter = reporter

        keystone_settings = muranoconductor.config.CONF.keystone
        heat_settings = muranoconductor.config.CONF.heat
        quantum_settings = muranoconductor.config.CONF.quantum

        client = ksclient.Client(
            endpoint=keystone_settings.auth_url,
            cacert=keystone_settings.ca_file or None,
            cert=keystone_settings.cert_file or None,
            key=keystone_settings.key_file or None,
            insecure=keystone_settings.insecure)

        if not client.authenticate(
                auth_url=keystone_settings.auth_url,
                tenant_id=tenant_id,
                token=token):
            raise heatclient.exc.HTTPUnauthorized()

        heat_url = client.service_catalog.url_for(
            service_type='orchestration',
            endpoint_type=heat_settings.endpoint_type)

        quantum_url = client.service_catalog.url_for(
            service_type='network',
            endpoint_type=quantum_settings.endpoint_type)

        self._quantum_client = quantum_client.Client(
            endpoint_url=quantum_url,
            token=token,
            ca_certs=quantum_settings.ca_cert or None,
            insecure=quantum_settings.insecure)

        self._heat_client = heat_client.Client(
            '1',
            heat_url,
            token_only=True,
            token=client.auth_token,
            ca_file=heat_settings.ca_file or None,
            cert_file=heat_settings.cert_file or None,
            key_file=heat_settings.key_file or None,
            insecure=heat_settings.insecure)

    def execute(self, command, callback, **kwargs):
        log.debug('Got command {0} on stack {1}'.format(command, self._stack))

        if command == 'CreateOrUpdate':
            return self._execute_create_update(
                kwargs['template'],
                muranoconductor.helpers.str2unicode(
                    kwargs.get('mappings') or {}),
                muranoconductor.helpers.str2unicode(
                    kwargs.get('arguments') or {}),
                callback)
        elif command == 'Delete':
            return self._execute_delete(callback)

    def _execute_create_update(self, template, mappings, arguments, callback):
        with open('data/templates/cf/%s.template' % template) as template_file:
            template_data = template_file.read()
        if not 'externalNetworkId' in mappings:
            mappings['externalNetworkId'] = self._get_external_network_id()
        template_data = muranoconductor.helpers.transform_json(
            anyjson.loads(template_data), mappings)

        self._update_pending_list.append({
            'template': template_data,
            'arguments': arguments,
            'callback': callback
        })

    def _execute_delete(self, callback):
        self._delete_pending_list.append({
            'callback': callback
        })

    def _get_external_network_id(self):
        log.info('Fetching the list of external networks...')
        ext_nets = self._quantum_client.list_networks(
            **{'router:external': True}).get('networks')
        log.debug(ext_nets)
        if ext_nets and len(ext_nets) > 0:
            if len(ext_nets) > 1:
                log.warning(
                    'Multiple external networks found, will use the first one')
            net = ext_nets[0]
            return net.get('id')
        else:
            log.error('No external networks found!')
            return None

    def has_pending_commands(self):
        return len(self._update_pending_list) + len(
            self._delete_pending_list) > 0

    def execute_pending(self):
        # wait for the stack not to be IN_PROGRESS
        self._wait_state(lambda status: True)
        r1 = self._execute_pending_updates()
        r2 = self._execute_pending_deletes()
        return r1 or r2

    def _execute_pending_updates(self):
        if not len(self._update_pending_list):
            return False

        try:
            template, arguments = self._get_current_template()
            stack_exists = (template != {})
            # do not need to merge with current stack cause we rebuilding it
            # from scratch on every deployment
            template, arguments = ({}, {})

            for t in self._update_pending_list:
                template = muranoconductor.helpers.merge_dicts(template,
                                                               t['template'])
                arguments = muranoconductor.helpers.merge_dicts(arguments,
                                                                t['arguments'],
                                                                max_levels=1)
            log.info(
                'Executing heat template {0} with arguments {1} on stack {2}'
                .format(anyjson.dumps(template), arguments, self._stack))

            if stack_exists:
                self._heat_client.stacks.update(
                    stack_id=self._stack,
                    parameters=arguments,
                    template=template)
                log.debug(
                    'Waiting for the stack {0} to be update'.format(
                        self._stack))
                outs = self._wait_state(
                    lambda status: status == 'UPDATE_COMPLETE')
                log.info('Stack {0} updated'.format(self._stack))
            else:
                self._heat_client.stacks.create(
                    stack_name=self._stack,
                    parameters=arguments,
                    template=template,
                    disable_rollback=False)

                log.debug('Waiting for the stack {0} to be create'.format(
                    self._stack))
                outs = self._wait_state(
                    lambda status: status == 'CREATE_COMPLETE')
                log.info('Stack {0} created'.format(self._stack))

            pending_list = self._update_pending_list
            self._update_pending_list = []

            for item in pending_list:
                item['callback'](outs)
            return True
        except Exception as ex:
            pending_list = self._update_pending_list
            self._update_pending_list = []
            for item in pending_list:
                item['callback'](None, ex)
            return True

    def _execute_pending_deletes(self):
        if not len(self._delete_pending_list):
            return False

        log.debug('Deleting stack {0}'.format(self._stack))
        try:
            self._heat_client.stacks.delete(
                stack_id=self._stack)
            log.debug(
                'Waiting for the stack {0} to be deleted'.format(self._stack))
            self._wait_state(
                lambda status: status in ('DELETE_COMPLETE', 'NOT_FOUND'))
            log.info('Stack {0} deleted'.format(self._stack))
        except Exception as ex:
            log.exception(ex)

        pending_list = self._delete_pending_list
        self._delete_pending_list = []

        for item in pending_list:
            item['callback'](True)
        return True

    def _get_current_template(self):
        try:
            stack_info = self._heat_client.stacks.get(stack_id=self._stack)
            template = self._heat_client.stacks.template(
                stack_id='{0}/{1}'.format(
                    stack_info.stack_name,
                    stack_info.id))
            return template, stack_info.parameters
        except heatclient.exc.HTTPNotFound:
            return {}, {}

    def _wait_state(self, status_func):
        tries = 4
        delay = 1
        while tries > 0:
            while True:
                try:
                    stack_info = self._heat_client.stacks.get(
                        stack_id=self._stack)
                    status = stack_info.stack_status
                    tries = 4
                    delay = 1
                except heatclient.exc.HTTPNotFound:
                    stack_info = None
                    status = 'NOT_FOUND'
                except Exception:
                    tries -= 1
                    delay *= 2
                    if not tries:
                        raise
                    eventlet.sleep(delay)
                    break

                if 'IN_PROGRESS' in status:
                    eventlet.sleep(2)
                    continue
                if not status_func(status):
                    raise EnvironmentError(
                        'Unexpected stack state {0}'.format(status))

                try:
                    return dict([(t['output_key'], t['output_value'])
                                 for t in stack_info.outputs])
                except Exception:
                    return {}
        return {}
