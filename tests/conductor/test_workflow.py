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
import os
import unittest

import deep
import mock
import mockfs

from conductor.workflow import Workflow


def load_sample(name):
    with mockfs.storage.original_open(os.path.join(
            os.path.dirname(__file__),
            'sample_data',
            name)) as sample_file:
        return sample_file.read()


class TestWorkflow(unittest.TestCase):
    def setUp(self):
        self.mfs = mockfs.replace_builtins()
        self.model = json.loads(load_sample('objectModel1.json'))
        self.original_model = json.loads(load_sample('objectModel1.json'))

    def tearDown(self):
        mockfs.restore_builtins()

    def _execute_workflow(self, xml):
        self.mfs.add_entries({'test': xml})
        stub = mock.MagicMock()
        stub.side_effect = RuntimeError
        workflow = Workflow('test', self.model, stub, stub, stub)
        workflow.execute()

    def test_empty_workflow_leaves_object_model_unchanged(self):
        xml = '<workflow/>'
        self._execute_workflow(xml)
        self.assertIsNone(deep.diff(self.original_model, self.model))

    def test_modifying_object_model_from_workflow(self):
        xml = '''
            <workflow>
                <rule match="$.services[*][?(@.id ==
                    '9571747991184642B95F430A014616F9'
                    and not @.state.invalid)]">
                    <set path="state.invalid">value</set>
                </rule>
            </workflow>
        '''
        self.assertNotIn(
            'state',
            self.model['services']['activeDirectories'][0])

        self._execute_workflow(xml)

        self.assertEqual(
            self.model['services']['activeDirectories'][0]['state']['invalid'],
            'value')

        self.assertIsNotNone(deep.diff(self.original_model, self.model))
        del self.model['services']['activeDirectories'][0]['state']
        self.assertIsNone(deep.diff(self.original_model, self.model))

    def test_selecting_properties_from_object_model_within_workflow(self):
        xml = '''
            <workflow>
                <rule match="$.services[*][?(@.id ==
                    '9571747991184642B95F430A014616F9'
                    and not @.test)]">
                    <set path="test">
                        Domain <select
                        path="domain"/> with primary DC <select
                        path="units.0.name"/>
                    </set>
                </rule>
            </workflow>
        '''

        self._execute_workflow(xml)
        self.assertEqual(
            self.model['services']['activeDirectories'][0]['test'],
            'Domain acme.loc with primary DC dc01')

