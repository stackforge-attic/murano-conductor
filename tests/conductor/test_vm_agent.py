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

import unittest
import mock
import mockfs
import json

from muranoconductor.commands.vm_agent import VmAgentExecutor


class TestVmAgent(unittest.TestCase):
    def setUp(self):
        self.mfs = mockfs.replace_builtins()
        self.template = {
            "Scripts": [
                "Get-DnsListeningIpAddress.ps1",
                "Join-Domain.ps1"
            ],
            "Commands": [
                {
                    "Name": "Get-DnsListeningIpAddress",
                    "Arguments": {}
                }],
            "RebootOnCompletion": 0
        }

        self.mfs.add_entries({
            './data/templates/agent/test.template':
            json.dumps(self.template),
            './data/templates/agent/scripts/Get-DnsListeningIpAddress.ps1':
            'function GetDNSip(){\ntest\n}\n',
            './data/templates/agent/scripts/Join-Domain.ps1':
            'function JoinDomain(){\ntest\n}\n',
        })
        self.template_path = './data/templates/agent/test.template'

    def test_script_encode(self):
        stack = mock.MagicMock()
        rmqclient = mock.MagicMock()
        reporter = mock.MagicMock()
        rmqclient.declare = mock.Mock()

        executor = VmAgentExecutor(stack, rmqclient, reporter)
        result, plan_id = executor.build_execution_plan(
            self.template_path)
        encoded = [
            'ZnVuY3Rpb24gR2V0RE5TaXAoKXsKdGVzdAp9Cg==\n',
            'ZnVuY3Rpb24gSm9pbkRvbWFpbigpewp0ZXN0Cn0K\n'
        ]
        self.assertEqual(result['Scripts'], encoded,
                         'Encoded script is incorrect')
