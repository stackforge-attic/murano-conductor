# Copyright (c) 2014 Mirantis Inc.
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
from muranoconductor.dsl import namespaces


class TestNamespaceResolving(unittest.TestCase):
    def setUp(self):
        self.resolver = namespaces.NamespaceResolver({
            '=': 'com.example.murano',
            'sys': 'com.example.murano.system',
            'heat': 'org.openstack.heat'
        })
        self.empty_resolver = namespaces.NamespaceResolver({})

    def test_invalid_names(self):
        self.assertRaises(ValueError, self.resolver.resolve_name, None)
        invalid_names = ['sys:',
                         'sys:excessive_ns:muranoResource',
                         'sys:excessive_ns:even_more_excessive:someResource']
        for name in invalid_names:
            self.assertRaises(NameError, self.resolver.resolve_name, name)

        self.assertRaises(KeyError, self.resolver.resolve_name,
                          'unknown_prefix:example.murano')

    def test_valid_names(self):
        name_wo_colons = 'some.arbitrary.name'
        self.assertEqual(self.resolver.resolve_name(':' + name_wo_colons),
                         name_wo_colons)

        self.assertEqual(self.resolver.resolve_name('sys:File'),
                         'com.example.murano.system.File')
        self.assertEqual(self.resolver.resolve_name('heat:Stack'),
                         'org.openstack.heat.Stack')
        self.assertEqual(self.resolver.resolve_name('Resource'),
                         'com.example.murano.Resource')
        self.assertEqual(self.resolver.resolve_name('Resource', 'com.base'),
                         'com.base.Resource')

        self.assertEqual(self.empty_resolver.resolve_name('File', 'com.base'),
                         'com.base.File')
        self.assertEqual(self.empty_resolver.resolve_name('Resource'),
                         'Resource')
