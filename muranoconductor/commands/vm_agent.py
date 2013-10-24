import uuid
import yaml
import os
import types

from muranoconductor.openstack.common import log as logging
from muranocommon.messaging import Message
import muranoconductor.helpers
from command import CommandBase
from muranocommon.helpers.token_sanitizer import TokenSanitizer

log = logging.getLogger(__name__)


class VmAgentExecutor(CommandBase):
    def __init__(self, stack, rmqclient, reporter, metadata_id):
        self._stack = stack
        self._rmqclient = rmqclient
        self._pending_list = []
        self._results_queue = '-execution-results-%s' % str(stack).lower()
        self._reporter = reporter
        rmqclient.declare(self._results_queue)

    def execute(self, template, mappings, unit, service, callback, metadata_id,
                timeout=None):
        template_path = '{0}/templates/agent/{1}.template'.format(metadata_id,
                                                                  template)

        #with open(template_path) as t_file:
        #    template_data = t_file.read()
        #
        #json_template = json.loads(template_data)
        #json_template = self.encode_scripts(json_template, template_path)
        template, msg_id = self.build_execution_plan(template_path)

        template = muranoconductor.helpers.transform_json(
            template, mappings)

        queue = ('%s-%s-%s' % (self._stack, service, unit)).lower()
        self._pending_list.append({
            'id': msg_id,
            'callback': callback,
            'timeout': timeout
        })

        msg = Message()
        msg.body = template
        msg.id = msg_id
        self._rmqclient.declare(queue)
        self._rmqclient.send(message=msg, key=queue)
        log.info('Sending RMQ message {0} to {1} with id {2}'.format(
            TokenSanitizer().sanitize(template), queue, msg_id))

    def build_execution_plan(self, path):
        with open(path) as stream:
            template = yaml.load(stream)
        if not isinstance(template, types.DictionaryType):
            raise ValueError('Incorrect execution plan ' + path)
        format_version = template.get('FormatVersion')
        if not format_version or format_version.startswith('1.'):
            return self._build_v1_execution_plan(template, path)
        else:
            return self._build_v2_execution_plan(template, path)

    def _build_v1_execution_plan(self, template, path):
        scripts_folder = os.path.join(
            os.path.dirname(path), 'scripts')
        script_files = template.get('Scripts', [])
        scripts = []
        for script in script_files:
            script_path = os.path.join(scripts_folder, script)
            log.debug('Loading script "{0}"'.format(script_path))
            with open(script_path) as script_file:
                script_data = script_file.read()
                scripts.append(script_data.encode('base64'))
        template['Scripts'] = scripts
        return template, uuid.uuid4().hex

    def _build_v2_execution_plan(self, template, path):
        scripts_folder = os.path.join(
            os.path.dirname(path), 'scripts')
        plan_id = uuid.uuid4().hex
        template['ID'] = plan_id
        if 'Action' not in template:
            template['Action'] = 'Execute'
        if 'Files' not in template:
            template['Files'] = {}

        files = {}
        for file_id, file_descr in template['Files'].items():
            files[file_descr['Name']] = file_id
        for name, script in template.get('Scripts', {}).items():
            if 'EntryPoint' not in script:
                raise ValueError('No entry point in script ' + name)
            script['EntryPoint'] = self._place_file(
                scripts_folder, script['EntryPoint'], template, files)
            if 'Files' in script:
                for i in range(0, len(script['Files'])):
                    script['Files'][i] = self._place_file(
                        scripts_folder, script['Files'][i], template, files)

        return template, plan_id

    def _place_file(self, folder, name, template, files):
        use_base64 = False
        if name.startswith('<') and name.endswith('>'):
            use_base64 = True
            name = name[1:len(name) - 1]
        if name in files:
            return files[name]

        file_id = uuid.uuid4().hex
        body_type = 'Base64' if use_base64 else 'Text'
        with open(os.path.join(folder, name)) as stream:
            body = stream.read()
        if use_base64:
            body = body.encode('base64')

        template['Files'][file_id] = {
            'Name': name,
            'BodyType': body_type,
            'Body': body
        }
        files[name] = file_id
        return file_id

    def has_pending_commands(self):
        return len(self._pending_list) > 0

    def execute_pending(self):
        if not self.has_pending_commands():
            return False

        with self._rmqclient.open(self._results_queue) as subscription:
            while self.has_pending_commands():
                # TODO: Add extended initialization timeout
                # By now, all the timeouts are defined by the command input
                # however, the first reply which we wait for being returned
                # from the unit may be delayed due to long unit initialization
                # and startup. So, for the nonitialized units we need to extend
                # the command's timeout with the initialization timeout
                timeout = self.get_max_timeout()
                if timeout:
                    span_message = "for {0} seconds".format(timeout)
                else:
                    span_message = 'infinitely'
                log.debug("Waiting %s for responses to be returned"
                          " by the agent. %i total responses remain",
                          span_message, len(self._pending_list))
                msg = subscription.get_message(timeout=timeout)
                if msg:
                    msg.ack()
                    msg_id = msg.body.get('SourceID', msg.id)
                    item, index = muranoconductor.helpers.find(
                        lambda t: t['id'] == msg_id, self._pending_list)
                    if item:
                        self._pending_list.pop(index)
                        item['callback'](msg.body)
                else:
                    while self.has_pending_commands():
                        item = self._pending_list.pop()
                        item['callback'](AgentTimeoutException(timeout))
        return True

    def get_max_timeout(self):
        res = 0
        for item in self._pending_list:
            if item['timeout'] is None:  # if at least 1 item has no timeout
                return None              # then return None (i.e. infinite)
            res = max(res, item['timeout'])
        return res


class AgentTimeoutException(Exception):
    def __init__(self, timeout):
        self.message = "Unable to receive any response from the agent" \
                       " in {0} sec".format(timeout)
        self.timeout = timeout


class UnhandledAgentException(Exception):
    def __init__(self, errors):
        self.message = "An unhandled exception has " \
                       "occurred in the Agent: {0}".format(errors)
        self.errors = errors
