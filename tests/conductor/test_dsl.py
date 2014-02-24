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
from muranoconductor.dsl import consts
from muranoconductor.dsl import classes
from muranoconductor.dsl import typespec


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


class TestClassHandling(unittest.TestCase):
    def setUp(self):
        self.resolver = namespaces.NamespaceResolver({
            '=': 'com.example.murano',
            'sys': 'com.example.murano.system',
            'heat': 'org.openstack.heat'
        })

        self.root_class = classes.MuranoClass(
            mock.Mock(), self.resolver, consts.ROOT_CLASS,
            ['You should not see me!'])
        self.class_loader = mock.Mock(get_class=lambda name: self.root_class)

        self.non_root_classes = {
            'DescendantClassWoParent': classes.MuranoClass(
                self.class_loader, self.resolver, 'DescendantClassWoParent'),
            'DescendantClassWParent': classes.MuranoClass(
                self.class_loader, self.resolver, 'DescendantClassWParent',
                [self.root_class])
        }

        self.descendant_class = self.non_root_classes['DescendantClassWParent']
        self.all_classes = {
            consts.ROOT_CLASS: self.root_class,
        }
        self.all_classes.update(self.non_root_classes)

    def test_class_name(self):
        for class_name, class_instance in self.all_classes.iteritems():
            actual_name = self.resolver.resolve_name(class_name)

            self.assertEqual(actual_name, class_instance.name)

    def test_class_namespace_resolver(self):
        self.assertEqual(self.resolver, self.root_class.namespace_resolver)

    def test_class_parents(self):
        self.assertEqual(self.root_class.parents, [])
        for class_name, class_instance in self.non_root_classes.iteritems():
            self.assertEqual(class_instance.parents, [self.root_class])

    def test_class_initial_properties(self):
        self.assertEqual(self.root_class.properties, [])

    def test_fails_add_incompatible_property_to_class(self):
        self.assertRaises(TypeError, self.root_class.add_property,
                          name='sampleProperty', property_typespec={})

    def test_add_property_to_class(self):
        prop = typespec.PropertySpec({'Default': 1}, self.resolver)
        self.root_class.add_property('firstPrime', prop)

        class_properties = self.root_class.properties
        class_property = self.root_class.get_property('firstPrime')

        self.assertEqual(class_properties, ['firstPrime'])
        self.assertEqual(class_property, prop)

    def test_class_property_search(self):
        void_prop = typespec.PropertySpec({'Default': 'Void'}, self.resolver)
        mother_prop = typespec.PropertySpec({'Default': 'Mother'},
                                            self.resolver)
        father_prop = typespec.PropertySpec({'Default': 'Father'},
                                            self.resolver)
        child_prop = typespec.PropertySpec({'Default': 'Child'},
                                           self.resolver)
        mother = self.non_root_classes['DescendantClassWoParent']
        father = self.non_root_classes['DescendantClassWParent']
        child = classes.MuranoClass(
            self.class_loader, self.resolver, 'LastDescendant',
            [mother, father])

        self.root_class.add_property('Void', void_prop)
        mother.add_property('Mother', mother_prop)
        father.add_property('Father', father_prop)
        child.add_property('Child', child_prop)

        self.assertEqual(child.find_property('Child'),
                         child_prop)
        self.assertEqual(child.find_property('Father'),
                         father_prop)
        self.assertEqual(child.find_property('Mother'),
                         mother_prop)
        self.assertEqual(child.find_property('Void'),
                         void_prop)

    def test_new_obj_compatible_with_class(self):
        obj_store = mock.Mock()
        context = mock.Mock()
        root_obj = self.root_class.new(None, obj_store, context)
        descendant_obj = self.descendant_class.new(
            root_obj, obj_store, context)

        self.assertTrue(self.root_class.is_compatible(root_obj))
        self.assertTrue(self.root_class.is_compatible(self.root_class))
        self.assertTrue(self.root_class.is_compatible(descendant_obj))
        self.assertFalse(self.descendant_class.is_compatible(root_obj))
