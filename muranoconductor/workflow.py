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
import logging

import jsonpath
import re
import types

import function_context
import xml_code_engine

log = logging.getLogger(__name__)
object_id = id


class Workflow(object):
    def __init__(self, filename, data, command_dispatcher, config, reporter):
        self._data = data
        self._engine = xml_code_engine.XmlCodeEngine()
        with open(filename) as xml:
            self._engine.load(xml)
        self._command_dispatcher = command_dispatcher
        self._config = config
        self._reporter = reporter

        # format: (rule-id, entity-id) => True for auto-reset bans,
        #                                 False for permanent bans
        self._blacklist = {}

    def execute(self):
        context = function_context.Context()
        context['/dataSource'] = self._data
        context['/commandDispatcher'] = self._command_dispatcher
        context['/config'] = self._config
        context['/reporter'] = self._reporter
        context['/__blacklist'] = self._blacklist
        return self._engine.execute(context)

    def prepare(self):
        permanent_bans = dict([
            (key, value) for key, value
            in self._blacklist.iteritems()
            if value is False
        ])
        self._blacklist.clear()
        self._blacklist.update(permanent_bans)

    @staticmethod
    def _get_path(obj, path, create_non_existing=False):
        current = obj
        for part in path:
            if isinstance(current, types.ListType):
                current = current[int(part)]
            elif isinstance(current, types.DictionaryType):
                if part not in current:
                    if create_non_existing:
                        current[part] = {}
                    else:
                        return None
                current = current[part]
            else:
                raise ValueError()

        return current

    @staticmethod
    def _set_path(obj, path, value):
        current = Workflow._get_path(obj, path[:-1], True)
        if isinstance(current, types.ListType):
            current[int(path[-1])] = value
        elif isinstance(current, types.DictionaryType):
            current[path[-1]] = value
        else:
            raise ValueError()

    @staticmethod
    def _get_relative_position(path, context):
        position = context['__dataSource_currentPosition'] or []

        index = 0
        for c in path:
            if c == ':':
                if len(position) > 0:
                    position = position[:-1]
            elif c == '/':
                position = []
            else:
                break

            index += 1

        return position, path[index:]

    @staticmethod
    def _correct_position(path, context):
        position, suffix = Workflow._get_relative_position(path, context)

        if not suffix:
            return position
        else:
            return position + suffix.split('.')

    @staticmethod
    def _select_func(context, path='', source=None, default=None, **kwargs):

        result = None
        if path.startswith('##'):
            config = context['/config']
            result = config[path[2:]]
        elif path.startswith('#'):
            result = context[path[1:]]
        elif source is not None:
            result = Workflow._get_path(
                context[source], path.split('.'))
        else:
            result = Workflow._get_path(
                context['/dataSource'],
                Workflow._correct_position(path, context))

        if not result and default is not None:
            result = default

        return result

    @staticmethod
    def _set_func(path, context, body, engine, target=None, **kwargs):
        body_data = engine.evaluate_content(body, context)

        if path.startswith('##'):
            raise RuntimeError('Cannot modify config from XML-code')
        elif path.startswith('#'):
            context_path = ':' + path[1:]
            log.debug(
                "Setting context variable '{0}' to '{1}'".format(context_path,
                                                                 body_data))
            context[context_path] = body_data
            return
        if target:
            data = context[target]
            position = path.split('.')
            if Workflow._get_path(data, position) != body_data:
                log.debug("Setting '{0}' to '{1}'".format(path, body_data))
                Workflow._set_path(data, position, body_data)
                context['/hasSideEffects'] = True

        else:
            data = context['/dataSource']
            new_position = Workflow._correct_position(path, context)
            if Workflow._get_path(data, new_position) != body_data:
                log.debug("Setting '{0}' to '{1}'".format(path, body_data))
                Workflow._set_path(data, new_position, body_data)
                context['/hasSideEffects'] = True

    @staticmethod
    def _mute_func(context, rule=None, id=None, **kwargs):
        if rule is None:
            rule = context['__currentRuleId']
        if id is None:
            id = context['__dataSource_currentObj']

        blacklist = context['/__blacklist']
        blacklist[(rule, id)] = False

    @staticmethod
    def _unmute_func(context, rule=None, id=None, **kwargs):
        if rule is None:
            rule = context['__currentRuleId']
        if id is None:
            id = context['__dataSource_currentObj']

        blacklist = context['/__blacklist']
        if (rule, id) in blacklist:
            del blacklist[(rule, id)]

    @staticmethod
    def _rule_func(match, context, body, engine, limit=0, id=None, desc=None,
                   **kwargs):
        if not id:
            id = object_id(body)
        context['__currentRuleId'] = id
        position, match = Workflow._get_relative_position(match, context)
        if not desc:
            desc = match
        data = Workflow._get_path(context['/dataSource'], position)
        match = re.sub(r'@\.([\w.]+)',
                       r"Workflow._get_path(@, '\1'.split('.'))", match)
        match = match.replace('$.', '$[*].')
        selected = jsonpath.jsonpath([data], match, 'IPATH') or []
        index = 0
        blacklist = context['/__blacklist']
        for found_match in selected:
            if 0 < int(limit) <= index:
                break
            index += 1
            new_position = position + found_match[1:]
            context['__dataSource_currentPosition'] = new_position
            cur_obj = Workflow._get_path(context['/dataSource'], new_position)

            use_blacklist = False
            if isinstance(cur_obj, dict) and ('id' in cur_obj):
                use_blacklist = True
                if (id, cur_obj['id']) in blacklist:
                    continue

            context['__dataSource_currentObj'] = cur_obj
            log.debug("Rule '{0}' matches on '{1}'".format(desc, cur_obj))
            for element in body:
                if element.tag == 'empty':
                    continue
                if use_blacklist:
                    blacklist[(id, cur_obj['id'])] = True
                engine.evaluate(element, context)
                if element.tag == 'rule' and context['/hasSideEffects']:
                    break
        if not index:
            empty_handler = body.find('empty')
            if empty_handler is not None:
                log.debug("Running empty handler for rule '{0}'".format(desc))
                engine.evaluate_content(empty_handler, context)

    @staticmethod
    def _select_all_func(context, path='', source=None, limit=0, **kwargs):
        if not source:
            position, path = Workflow._get_relative_position(path, context)
            source = Workflow._get_path(context['/dataSource'], position)
        result = jsonpath.jsonpath(source, path) or []
        return result if not limit else result[:limit]

    @staticmethod
    def _select_single_func(context, path='', source=None, **kwargs):
        result = Workflow._select_all_func(context, path, source, **kwargs)
        return result[0] if len(result) >= 1 else None

    @staticmethod
    def _workflow_func(context, body, engine, **kwargs):
        context['/hasSideEffects'] = False
        for element in body:
            engine.evaluate(element, context)
            if element.tag == 'rule' and context['/hasSideEffects']:
                return True
        return False

    @staticmethod
    def _stop_func(context, body, engine, **kwargs):
        if not 'temp' in context['/dataSource']:
            context['/dataSource']['temp'] = {}

        context['/dataSource']['temp']['_stop_requested'] = True


xml_code_engine.XmlCodeEngine.register_function(
    Workflow._rule_func, 'rule')

xml_code_engine.XmlCodeEngine.register_function(
    Workflow._workflow_func, 'workflow')

xml_code_engine.XmlCodeEngine.register_function(
    Workflow._set_func, 'set')

xml_code_engine.XmlCodeEngine.register_function(
    Workflow._select_func, 'select')

xml_code_engine.XmlCodeEngine.register_function(
    Workflow._stop_func, 'stop')

xml_code_engine.XmlCodeEngine.register_function(
    Workflow._select_all_func, 'select-all')

xml_code_engine.XmlCodeEngine.register_function(
    Workflow._select_single_func, 'select-single')

xml_code_engine.XmlCodeEngine.register_function(
    Workflow._mute_func, 'mute')

xml_code_engine.XmlCodeEngine.register_function(
    Workflow._unmute_func, 'unmute')
