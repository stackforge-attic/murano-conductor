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
import bunch
from muranoconductor.engine import namespaces
from muranoconductor.engine import consts
from muranoconductor.engine import classes
from muranoconductor.engine import typespec
from muranoconductor.engine import objects


class TestNamespaceResolving(unittest.TestCase):
    def test_fails_w_empty_name(self):
        resolver = namespaces.NamespaceResolver({'=': 'com.example.murano'})

        self.assertRaises(ValueError, resolver.resolve_name, None)

    def test_fails_w_unknown_prefix(self):
        resolver = namespaces.NamespaceResolver({'=': 'com.example.murano'})
        name = 'unknown_prefix:example.murano'

        self.assertRaises(KeyError, resolver.resolve_name, name)

    def test_fails_w_prefix_wo_name(self):
        resolver = namespaces.NamespaceResolver({'=': 'com.example.murano'})
        name = 'sys:'

        self.assertRaises(NameError, resolver.resolve_name, name)

    def test_fails_w_excessive_prefix(self):
        ns = {'sys': 'com.example.murano.system'}
        resolver = namespaces.NamespaceResolver(ns)
        invalid_name = 'sys:excessive_ns:muranoResource'

        self.assertRaises(NameError, resolver.resolve_name, invalid_name)

    def test_cuts_empty_prefix(self):
        resolver = namespaces.NamespaceResolver({'=': 'com.example.murano'})
        # name without prefix delimiter
        name = 'some.arbitrary.name'

        resolved_name = resolver.resolve_name(':' + name)

        self.assertEqual(name, resolved_name)

    def test_resolves_specified_ns_prefix(self):
        ns = {'sys': 'com.example.murano.system'}
        resolver = namespaces.NamespaceResolver(ns)
        short_name, full_name = 'sys:File', 'com.example.murano.system.File'

        resolved_name = resolver.resolve_name(short_name)

        self.assertEqual(full_name, resolved_name)

    def test_resolves_current_ns(self):
        resolver = namespaces.NamespaceResolver({'=': 'com.example.murano'})
        short_name, full_name = 'Resource', 'com.example.murano.Resource'

        resolved_name = resolver.resolve_name(short_name)

        self.assertEqual(full_name, resolved_name)

    def test_resolves_explicit_base(self):
        resolver = namespaces.NamespaceResolver({'=': 'com.example.murano'})

        resolved_name = resolver.resolve_name('Resource', relative='com.base')

        self.assertEqual('com.base.Resource', resolved_name)

    def test_resolves_explicit_base_w_empty_namespaces(self):
        resolver = namespaces.NamespaceResolver({})

        resolved_name = resolver.resolve_name('File', 'com.base')

        self.assertEqual('com.base.File', resolved_name)

    def test_resolves_w_empty_namespaces(self):
        resolver = namespaces.NamespaceResolver({})

        resolved_name = resolver.resolve_name('Resource')

        self.assertEqual('Resource', resolved_name)


class TestClassHandling(unittest.TestCase):
    resolver = mock.Mock(resolve_name=lambda name: name)

    def test_class_name(self):
        cls = classes.MuranoClass(None, self.resolver, consts.ROOT_CLASS)

        self.assertEqual(consts.ROOT_CLASS, cls.name)

    def test_class_namespace_resolver(self):
        resolver = namespaces.NamespaceResolver({})
        cls = classes.MuranoClass(None, resolver, consts.ROOT_CLASS)

        self.assertEqual(resolver, cls.namespace_resolver)

    def test_root_class_has_no_parents(self):
        root_class = classes.MuranoClass(
            None, self.resolver, consts.ROOT_CLASS, ['You should not see me!'])

        self.assertEqual([], root_class.parents)

    def test_non_root_class_resolves_parents(self):
        root_cls = classes.MuranoClass(None, self.resolver, consts.ROOT_CLASS)
        class_loader = mock.Mock(get_class=lambda name: root_cls)
        desc_cls1 = classes.MuranoClass(class_loader, self.resolver, 'Obj')
        desc_cls2 = classes.MuranoClass(
            class_loader, self.resolver, 'Obj', [root_cls])

        self.assertEqual([root_cls], desc_cls1.parents)
        self.assertEqual([root_cls], desc_cls2.parents)

    def test_class_initial_properties(self):
        cls = classes.MuranoClass(None, self.resolver, consts.ROOT_CLASS)
        self.assertEqual([], cls.properties)

    def test_fails_add_incompatible_property_to_class(self):
        cls = classes.MuranoClass(None, self.resolver, consts.ROOT_CLASS)
        kwargs = {'name': 'sampleProperty', 'property_typespec': {}}

        self.assertRaises(TypeError, cls.add_property, **kwargs)

    def test_add_property_to_class(self):
        prop = typespec.PropertySpec({'Default': 1}, self.resolver)
        cls = classes.MuranoClass(None, self.resolver, consts.ROOT_CLASS)
        cls.add_property('firstPrime', prop)

        class_properties = cls.properties
        class_property = cls.get_property('firstPrime')

        self.assertEqual(['firstPrime'], class_properties)
        self.assertEqual(prop, class_property)

    def test_class_property_search(self):
        void_prop = typespec.PropertySpec({'Default': 'Void'}, self.resolver)
        mother_prop = typespec.PropertySpec({'Default': 'Mother'},
                                            self.resolver)
        father_prop = typespec.PropertySpec({'Default': 'Father'},
                                            self.resolver)
        child_prop = typespec.PropertySpec({'Default': 'Child'},
                                           self.resolver)
        root = classes.MuranoClass(None, self.resolver, consts.ROOT_CLASS)
        mother = classes.MuranoClass(None, self.resolver, 'Mother', [root])
        father = classes.MuranoClass(None, self.resolver, 'Father', [root])
        child = classes.MuranoClass(
            None, self.resolver, 'Child', [mother, father])

        root.add_property('Void', void_prop)
        mother.add_property('Mother', mother_prop)
        father.add_property('Father', father_prop)
        child.add_property('Child', child_prop)

        self.assertEqual(child_prop, child.find_property('Child'))
        self.assertEqual(father_prop, child.find_property('Father'))
        self.assertEqual(mother_prop, child.find_property('Mother'))
        self.assertEqual(void_prop, child.find_property('Void'))

    def test_class_is_compatible(self):
        cls = classes.MuranoClass(None, self.resolver, consts.ROOT_CLASS)
        descendant_cls = classes.MuranoClass(
            None, self.resolver, 'DescendantCls', [cls])
        obj, descendant_obj = mock.Mock(), mock.Mock()
        obj.__class__ = objects.MuranoObject
        descendant_obj.__class__ = objects.MuranoObject
        obj.type = cls
        descendant_obj.type = descendant_cls
        descendant_obj.parents = [obj]

        self.assertTrue(cls.is_compatible(obj))
        self.assertTrue(cls.is_compatible(descendant_obj))
        self.assertFalse(descendant_cls.is_compatible(obj))

    def test_new_method_calls_initialize(self):
        cls = classes.MuranoClass(None, self.resolver, consts.ROOT_CLASS)
        cls.object_class = mock.Mock()

        with mock.patch('inspect.getargspec') as spec_mock:
            spec_mock.return_value = bunch.bunchify({'args': ()})
            obj = cls.new(None, None, None, {'param': None})

            self.assertTrue(obj.initialize.called)

    def test_new_method_not_calls_initialize(self):
        cls = classes.MuranoClass(None, self.resolver, consts.ROOT_CLASS)
        cls.object_class = mock.Mock()

        obj = cls.new(None, None, None)

        self.assertFalse(obj.initialize.called)
