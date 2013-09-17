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
import os.path
import datetime
from muranoconductor.commands.windows_agent import AgentTimeoutException
from muranoconductor.commands.windows_agent import UnhandledAgentException

import xml_code_engine

from openstack.common import log as logging

log = logging.getLogger(__name__)


def send_command(engine, context, body, template, service, unit,
                 mappings=None, result=None, error=None, timeout=None,
                 osVersion=None, **kwargs):
    if not mappings:
        mappings = {}
    if osVersion:
        template = os.path.join(osVersion, template)
    command_dispatcher = context['/commandDispatcher']
    if timeout:
        timeout = int(timeout)

    def callback(result_value):
        log.info(
            'Received result from {2} for {0}: {1}'.format(
                template, result_value, unit))
        ok = []
        errors = []
        if isinstance(result_value, AgentTimeoutException):
            errors.append({
                'source': 'timeout',
                'message': result_value.message,
                'timeout': result_value.timeout,
                'timestamp': datetime.datetime.now().isoformat()
            })
        else:
            if result_value['IsException']:
                errors.append(dict(_get_exception_info(
                    result_value.get('Result', [])), source='execution_plan'))
            else:
                for res in result_value.get('Result', []):
                    if res['IsException']:
                        errors.append(dict(_get_exception_info(
                            res.get('Result', [])), source='command'))
                    else:
                        ok.append(res)

        if ok:
            if result is not None:
                context[result] = ok
            success_handler = body.find('success')
            if success_handler is not None:
                engine.evaluate_content(success_handler, context)
        if errors:
            if error is not None:
                context[error] = errors
            failure_handler = body.find('failure')
            if failure_handler is not None:
                log.warning(
                    'Handling errors ({0}) in failure block'.format(errors))
                engine.evaluate_content(failure_handler, context)
            else:
                log.error("No failure block found for errors", exc_info=True)
                if isinstance(result_value, AgentTimeoutException):
                    raise result_value
                else:
                    raise UnhandledAgentException(errors)

    command_dispatcher.execute(
        name='agent', template=template, mappings=mappings,
        unit=unit, service=service, callback=callback, timeout=timeout)


def _get_array_item(array, index):
    return array[index] if len(array) > index else None


def _get_exception_info(data):
    data = data or []
    return {
        'type': _get_array_item(data, 0),
        'message': _get_array_item(data, 1),
        'command': _get_array_item(data, 2),
        'details': _get_array_item(data, 3),
        'timestamp':  datetime.datetime.now().isoformat()
    }

xml_code_engine.XmlCodeEngine.register_function(send_command, "send-command")
