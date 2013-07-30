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

import json
import unittest

import mock
import mockfs
import heatclient.exc

from muranoconductor.commands.cloud_formation import HeatExecutor


class TestHeatExecutor(unittest.TestCase):
    def setUp(self):
        self.mfs = mockfs.replace_builtins()
        template = {
            "$name": {
                "$key": "$value"
            }
        }
        self.mfs.add_entries({
            './data/templates/cf/test.template': json.dumps(template)})

    def tearDown(self):
        mockfs.restore_builtins()

    def _init(self, config_mock, ksclient_mock):
        config_mock.heat.auth_url = 'http://invalid.url'

        auth_data = ksclient_mock().tokens.authenticate()
        auth_data.id = '123456'
        auth_data.serviceCatalog = [{
            'name': 'heat',
            'endpoints': [{'publicURL': 'http://invalid.heat.url'}]
        }]

    @mock.patch('heatclient.v1.client.Client')
    @mock.patch('keystoneclient.v2_0.client.Client')
    @mock.patch('muranoconductor.config.CONF')
    def test_create_stack(self, config_mock, ksclient_mock, heat_mock):
        self._init(config_mock, ksclient_mock)
        reporter = mock.MagicMock()
        executor = HeatExecutor('stack', 'token', 'tenant_id', reporter)
        callback = mock.MagicMock()

        executor.execute(
            template='test',
            command='CreateOrUpdate',
            mappings={
                'name': 'testName',
                'key': 'testKey',
                'value': 'testValue'},
            arguments={
                'arg1': 'arg1Value',
                'arg2': 'arg2Value'},
            callback=callback)

        heat_mock().stacks.get().stack_status = 'CREATE_COMPLETE'
        heat_mock().stacks.template = mock.MagicMock(
            side_effect=heatclient.exc.HTTPNotFound)

        self.assertTrue(executor.has_pending_commands())
        result = executor.execute_pending()
        self.assertTrue(result)
        heat_mock().stacks.create.assert_called_with(
            stack_name='stack',
            parameters={
                'arg1': 'arg1Value',
                'arg2': 'arg2Value'},
            template={
                "testName": {
                    "testKey": "testValue"
                }
            })
        callback.assert_called_with({})

    @mock.patch('heatclient.v1.client.Client')
    @mock.patch('keystoneclient.v2_0.client.Client')
    @mock.patch('muranoconductor.config.CONF')
    def test_update_stack(self, config_mock, ksclient_mock, heat_mock):
        self._init(config_mock, ksclient_mock)
        reporter = mock.MagicMock()
        executor = HeatExecutor('stack', 'token', 'tenant_id', reporter)
        callback = mock.MagicMock()

        executor.execute(
            template='test',
            command='CreateOrUpdate',
            mappings={
                'name': 'testName',
                'key': 'testKey',
                'value': 'testValue'},
            arguments={
                'arg1': 'arg1Value',
                'arg2': 'arg2Value'},
            callback=callback)

        get_mock = heat_mock().stacks.get()
        get_mock.stack_name = 'stack'
        get_mock.id = 'stack'
        get_mock.parameters = {}
        get_mock.stack_status = ''
        get_mock._status_index = 0

        def side_effect(*args, **kwargs):
            if get_mock._status_index < 2:
                get_mock.stack_status = 'IN_PROGRESS'
            else:
                get_mock.stack_status = 'UPDATE_COMPLETE'
            get_mock._status_index += 1
            return get_mock

        heat_mock().stacks.get = mock.MagicMock(side_effect=side_effect)
        heat_mock().stacks.template = mock.MagicMock(
            return_value={'instance': {}})

        self.assertTrue(executor.has_pending_commands())
        result = executor.execute_pending()
        self.assertTrue(result)
        heat_mock().stacks.update.assert_called_with(
            stack_id='stack',
            parameters={
                'arg1': 'arg1Value',
                'arg2': 'arg2Value'},
            template={
                'instance': {},
                "testName": {
                    "testKey": "testValue"
                }
            })
        callback.assert_called_with({})

    @mock.patch('heatclient.v1.client.Client')
    @mock.patch('keystoneclient.v2_0.client.Client')
    @mock.patch('muranoconductor.config.CONF')
    def test_delete_stack(self, config_mock, ksclient_mock, heat_mock):
        self._init(config_mock, ksclient_mock)
        reporter = mock.MagicMock()
        executor = HeatExecutor('stack', 'token', 'tenant_id', reporter)
        callback = mock.MagicMock()

        executor.execute(
            template='test',
            command='Delete',
            callback=callback)

        heat_mock().stacks.get = mock.MagicMock(
            side_effect=heatclient.exc.HTTPNotFound)

        self.assertTrue(executor.has_pending_commands())
        result = executor.execute_pending()
        self.assertTrue(result)
        heat_mock().stacks.delete.assert_called_with(stack_id='stack')
        callback.assert_called_with(True)
