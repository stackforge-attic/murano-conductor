#    Copyright (c) 2013 Mirantis, Inc.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.


class UsageOptions(object):
    In = 'In'
    Out = 'Out'
    InOut = 'InOut'
    Runtime = 'Runtime'
    Const = 'Const'
    All = {In, Out, InOut, Runtime, Const}
    Writable = {Out, InOut, Runtime}


class Spec(object):
    def __init__(self, declaration, namespace_resolver):
        self._namespace_resolver = namespace_resolver
        self._default = declaration.get('Default')
        self._has_default = 'Default' in declaration
        self._usage = declaration.get('Usage') or 'In'
        if self._usage not in UsageOptions.All:
            raise SyntaxError('Unknown type {0}. Must be one of ({1})'.format(
                self._usage, ', '.join(UsageOptions.All)))

    def validate(self, value, this, context,  object_store, default=None):
        return value

    @property
    def default(self):
        return self._default

    @property
    def has_default(self):
        return self._has_default

    @property
    def usage(self):
        return self._usage


class PropertySpec(Spec):
    pass


class ArgumentSpec(Spec):
    pass
