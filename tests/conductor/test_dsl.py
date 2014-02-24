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
from muranoconductor.dsl import namespaces


class TestNamespaceResolving(unittest.TestCase):
    def setUp(self):
        self.resolver = namespaces.NamespaceResolver({
            '=': 'com.example.murano',
            'sys': 'com.example.murano.system',
            'heat': 'org.openstack.heat'
        })
        self.empty_resolver = namespaces.NamespaceResolver({})

    def test_fails_w_empty_name(self):
        name = None

        self.assertRaises(ValueError, self.resolver.resolve_name, name)

    def test_fails_w_unknown_prefix(self):
        name = 'unknown_prefix:example.murano'

        self.assertRaises(KeyError, self.resolver.resolve_name, name)

    def test_fails_w_prefix_wo_name(self):
        name = 'sys:'

        self.assertRaises(NameError, self.resolver.resolve_name, name)

    def test_fails_w_excessive_prefix(self):
        invalid_names = ['sys:excessive_ns:muranoResource',
                         'sys:excessive_ns:even_more_excessive:someResource']

        for name in invalid_names:
            self.assertRaises(NameError, self.resolver.resolve_name, name)

    def test_cuts_empty_prefix(self):
        name_wo_prefix_delimiter = 'some.arbitrary.name'

        resolved_name = self.resolver.resolve_name(
            ':' + name_wo_prefix_delimiter)

        self.assertEqual(resolved_name, name_wo_prefix_delimiter)

    def test_resolves_specified_ns_prefix(self):
        names = {'sys:File': 'com.example.murano.system.File',
                 'heat:Stack': 'org.openstack.heat.Stack'}

        for ns_name, full_name in names.iteritems():
            resolved_name = self.resolver.resolve_name(ns_name)

            self.assertEqual(resolved_name, full_name)

    def test_resolves_current_ns(self):
        resolved_name = self.resolver.resolve_name('Resource')

        self.assertEqual(resolved_name, 'com.example.murano.Resource')

    def test_resolves_explicit_base(self):
        resolved_name = self.resolver.resolve_name('Resource', 'com.base')

        self.assertEqual(resolved_name, 'com.base.Resource')

    def test_resolves_explicit_base_w_empty_namespaces(self):
        resolved_name = self.empty_resolver.resolve_name('File', 'com.base')

        self.assertEqual(resolved_name, 'com.base.File')

    def test_resolves_w_empty_namespaces(self):
        resolved_name = self.empty_resolver.resolve_name('Resource')

        self.assertEqual(resolved_name, 'Resource')

