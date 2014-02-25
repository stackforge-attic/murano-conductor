#    Copyright (c) 2014 Mirantis, Inc.
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
from collections import OrderedDict
import inspect
import types
from muranoconductor.dsl.yaql_expression import YaqlExpression
import muranoconductor.dsl.typespec as typespec
import muranoconductor.dsl.expressions as expressions


class MuranoMethod(object):
    def __init__(self, namespace_resolver, murano_class, name, payload):
        self._name = name
        self._namespace_resolver = namespace_resolver

        if callable(payload):
            self._body = payload
            self._arguments_scheme = self._generate_arguments_scheme(payload)
        else:
            payload = payload or {}
            self._body = self._prepare_body(payload.get('Body') or [])
            arguments_scheme = payload.get('Arguments') or []
            if isinstance(arguments_scheme, types.DictionaryType):
                arguments_scheme = [{key: value} for key, value in
                                    arguments_scheme.iteritems()]
            self._arguments_scheme = OrderedDict()
            for record in arguments_scheme:
                if not isinstance(record, types.DictType) or len(record) > 1:
                    raise ValueError()
                name = record.keys()[0]
                self._arguments_scheme[name] = typespec.ArgumentSpec(
                    record[name], self._namespace_resolver)

        self._murano_class = murano_class

    @property
    def name(self):
        return self._name

    @property
    def murano_class(self):
        return self._murano_class

    @property
    def arguments_scheme(self):
        return self._arguments_scheme

    @property
    def body(self):
        return self._body

    def _generate_arguments_scheme(self, func):
        func_info = inspect.getargspec(func)
        data = [(name, {'Contract': YaqlExpression('$')})
                for name in func_info.args]
        if inspect.ismethod(func):
            data = data[1:]
        defaults = func_info.defaults or tuple()
        for i in xrange(len(defaults)):
            data[i + len(data) - len(defaults)][1]['Default'] = defaults[i]
        result = OrderedDict([(name, typespec.ArgumentSpec(
            declaration, self._namespace_resolver))
            for name, declaration in data])
        if '_context' in result:
            del result['_context']
        return result

    @staticmethod
    def _prepare_body(body):
        return expressions.CodeBlock(body)

    def __repr__(self):
        return 'MuranoMethod({0})'.format(self.name)
