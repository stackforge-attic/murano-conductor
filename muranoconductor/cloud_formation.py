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

import base64
import config
import random
import string
import time

import xml_code_engine
from openstack.common import log as logging

log = logging.getLogger(__name__)

def update_cf_stack(engine, context, body, template, result=None, error=None,
                    **kwargs):
    command_dispatcher = context['/commandDispatcher']

    def callback(result_value, error_result=None):
        if result is not None:
            context[result] = result_value

        if error_result is not None:
            if error is not None:
                context[error] = {
                    'message': getattr(error_result, 'message', None),
                    'strerror': getattr(error_result, 'strerror', None),
                    'timestamp': time.time()
                }
            failure_handler = body.find('failure')
            if failure_handler is not None:
                log.warning("Handling exception in failure block")
                engine.evaluate_content(failure_handler, context)
                return
            else:
                log.error("No failure block found for exception")
                raise error_result

        success_handler = body.find('success')
        if success_handler is not None:
            engine.evaluate_content(success_handler, context)

    command_dispatcher.execute(
        name='cf', command='CreateOrUpdate', template=template,
        mappings=kwargs.get('mappings', {}),
        arguments=kwargs.get('arguments', {}),
        callback=callback)


def delete_cf_stack(engine, context, body, **kwargs):
    command_dispatcher = context['/commandDispatcher']

    def callback(result_value):
        success_handler = body.find('success')
        if success_handler is not None:
            engine.evaluate_content(success_handler, context)

    command_dispatcher.execute(
        name='cf', command='Delete', callback=callback)


def prepare_user_data(context, hostname, service, unit,
                      template='Default', **kwargs):
    settings = config.CONF.rabbitmq

    with open('data/init.ps1') as init_script_file:
        with open('data/templates/agent-config/{0}.template'.format(
                template)) as template_file:
            init_script = init_script_file.read()
            template_data = template_file.read()

            replacements = {
                '%RABBITMQ_HOST%': settings.host,
                '%RABBITMQ_PORT%': settings.port,
                '%RABBITMQ_INPUT_QUEUE%': '-'.join(
                    ['e' + str(context['/dataSource']['id']),
                     str(service), str(unit)]).lower(),
                '%RESULT_QUEUE%': '-execution-results-e{0}'.format(
                    str(context['/dataSource']['id'])).lower(),
                '%RABBITMQ_USER%': settings.login,
                '%RABBITMQ_PASSWORD%': settings.password,
                '%RABBITMQ_VHOST%': settings.virtual_host,
                '%RABBITMQ_SSL%': 'true' if settings.ssl else 'false'
            }

            template_data = set_config_params(template_data, replacements)

            init_script = init_script.replace(
                '%WINDOWS_AGENT_CONFIG_BASE64%',
                base64.b64encode(template_data))

            init_script = init_script.replace('%INTERNAL_HOSTNAME%', hostname)
            init_script = init_script.replace(
                '%MURANO_SERVER_ADDRESS%',
                config.CONF.file_server or settings.host)

            return init_script


def set_config_params(template_data, replacements):
    for key in replacements:
        template_data = template_data.replace(key, str(replacements[key]))
    return template_data


counters = {}


def int2base(x, base):
    digs = string.digits + string.lowercase
    if x < 0:
        sign = -1
    elif x == 0:
        return '0'
    else:
        sign = 1
    x *= sign
    digits = []
    while x:
        digits.append(digs[x % base])
        x /= base
    if sign < 0:
        digits.append('-')
    digits.reverse()
    return ''.join(digits)


def generate_hostname(pattern, service_id, **kwargs):
    if not pattern:
        return _generate_random_hostname()
    elif '#' in pattern:
        counter = counters.get(service_id) or 1
        counters[service_id] = counter + 1
        return pattern.replace('#', str(counter), 1)
    else:
        return pattern


def _generate_random_hostname():
    counter = counters.get('') or 1
    prefix = ''.join(random.choice(string.lowercase) for _ in range(5))
    timestamp = int2base(int(time.time() * 1000), 36)[:8]
    suffix = int2base(counter, 36)
    counters[''] = (counter + 1) % 1296
    return prefix + timestamp + suffix


xml_code_engine.XmlCodeEngine.register_function(
    update_cf_stack, "update-cf-stack")

xml_code_engine.XmlCodeEngine.register_function(
    delete_cf_stack, "delete-cf-stack")

xml_code_engine.XmlCodeEngine.register_function(
    prepare_user_data, "prepare-user-data")

xml_code_engine.XmlCodeEngine.register_function(
    generate_hostname, "generate-hostname")
