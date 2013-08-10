import json
import uuid
import os

from muranoconductor.openstack.common import log as logging
from muranocommon.messaging import Message
import muranoconductor.helpers
from command import CommandBase

log = logging.getLogger(__name__)


class WindowsAgentExecutor(CommandBase):
    def __init__(self, stack, rmqclient, reporter):
        self._stack = stack
        self._rmqclient = rmqclient
        self._pending_list = []
        self._results_queue = '-execution-results-%s' % str(stack).lower()
        self._reporter = reporter
        rmqclient.declare(self._results_queue)

    def execute(self, template, mappings, unit, service, callback,
                timeout=None):
        template_path = 'data/templates/agent/%s.template' % template
        with open(template_path) as t_file:
            template_data = t_file.read()

        json_template = json.loads(template_data)
        json_template = self.encode_scripts(json_template, template_path)
        template_data = muranoconductor.helpers.transform_json(
            json_template, mappings)

        msg_id = str(uuid.uuid4()).lower()
        queue = ('%s-%s-%s' % (self._stack, service, unit)).lower()
        self._pending_list.append({
            'id': msg_id,
            'callback': callback,
            'timeout': timeout
        })

        msg = Message()
        msg.body = template_data
        msg.id = msg_id
        self._rmqclient.declare(queue)
        self._rmqclient.send(message=msg, key=queue)
        log.info('Sending RMQ message {0} to {1} with id {2}'.format(
            template_data, queue, msg_id))

    def encode_scripts(self, json_data, template_path):
        scripts_folder = ''.join([os.path.dirname(template_path), "/scripts/"])
        script_files = json_data.get("Scripts", [])
        scripts = []
        for script in script_files:
            script_path = os.path.join(scripts_folder, script)
            log.debug('Loading script "{0}"'.format(script_path))
            with open(script_path) as script_file:
                script_data = script_file.read()
                scripts.append(script_data.encode('base64'))
        json_data["Scripts"] = scripts
        return json_data

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
                    msg_id = msg.id.lower()
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
