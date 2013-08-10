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

from muranoconductor.commands.windows_agent import WindowsAgentExecutor 

class TestWindowsAgent(unittest.TestCase):
    def setUp(self):
        self.mfs = mockfs.replace_builtins()
        self.template = {
                    "Scripts": ["ask_dns_ip.ps1", "joinDomain.ps1" 
                                ],
                    "Commands": [
                    {
                     "Name": "Get-DnsListeningIpAddress",
                     "Arguments": {}
                     }
                                 ],
                    "RebootOnCompletion": 0
                    }

        self.mfs.add_entries({
            './data/templates/cf/test.template': json.dumps(self.template),
            './data/templates/cf/scripts/ask_dns_ip.ps1': 'function GetDNSip(){\ntest\n}\n',
            './data/templates/cf/scripts/joinDomain.ps1': 'function JoinDomain(){\ntest\n}\n',
            })
        self.template_path = './data/templates/cf/test.template' 

    
    def test_script_encode(self):
        stack = mock.MagicMock()
        rmqclient = mock.MagicMock()
        reporter = mock.MagicMock()
        rmqclient.declare = mock.Mock()
        
        executor = WindowsAgentExecutor(stack, rmqclient, reporter)
        result = executor.encode_scripts(self.template, self.template_path)
        encoded = ['ZnVuY3Rpb24gR2V0RE5TaXAoKXsKdGVzdAp9CmZ1bmN0aW9uIEpvaW5Eb21haW4oKXsKdGVzdAp9\nCg==\n']
        self.assertEqual(result['Scripts'], encoded, 'Encoded script is incorrect')
        

