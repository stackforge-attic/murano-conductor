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
import types
import muranoconductor.dsl.helpers as helpers
from muranoconductor.dsl.yaql_expression import YaqlExpression
from muranoconductor.dsl.lhs_expression import LhsExpression


class DslExpression(object):
    def execute(self, context, murano_class):
        pass


class Statement(DslExpression):
    def __init__(self, statement):
        if isinstance(statement, YaqlExpression):
            key = None
            value = statement
        elif isinstance(statement, types.DictionaryType):
            if len(statement) != 1:
                raise SyntaxError()
            key = statement.keys()[0]
            value = statement[key]
        else:
            raise SyntaxError()

        self._destination = None if not key else LhsExpression(key)
        self._expression = value

    @property
    def destination(self):
        return self._destination

    @property
    def expression(self):
        return self._expression

    def execute(self, context, murano_class):
        result = helpers.evaluate(self.expression, context)
        if self.destination:
            self.destination(result, context, murano_class)

        return result


def parse_expression(expr):
    result = None
    if isinstance(expr, YaqlExpression):
        result = Statement(expr)
    elif isinstance(expr, types.DictionaryType):
        kwds = {}
        for key, value in expr.iteritems():
            if isinstance(key, YaqlExpression):
                if result is not None:
                    raise ValueError()
                result = Statement(expr)
            else:
                kwds[key] = value

    if result is None:
        raise SyntaxError()
    return result


class CodeBlock(DslExpression):
    def __init__(self, body):
        if not isinstance(body, types.ListType):
            body = [body]
        self.code_block = map(parse_expression, body)

    def execute(self, context, murano_class):
        for expr in self.code_block:
            expr.execute(context, murano_class)
