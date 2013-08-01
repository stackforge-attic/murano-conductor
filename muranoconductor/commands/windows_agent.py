import json
import uuid

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

    def execute(self, template, mappings, unit, service, callback):
        with open('data/templates/agent/%s.template' % template) as t_file:
            template_data = t_file.read()

        template_data = muranoconductor.helpers.transform_json(
            json.loads(template_data), mappings)

        msg_id = str(uuid.uuid4()).lower()
        queue = ('%s-%s-%s' % (self._stack, service, unit)).lower()
        self._pending_list.append({
            'id': msg_id,
            'callback': callback
        })

        msg = Message()
        msg.body = template_data
        msg.id = msg_id
        self._rmqclient.declare(queue)
        self._rmqclient.send(message=msg, key=queue)
        log.info('Sending RMQ message {0} to {1} with id {2}'.format(
            template_data, queue, msg_id))

    def has_pending_commands(self):
        return len(self._pending_list) > 0

    def execute_pending(self):
        if not self.has_pending_commands():
            return False

        with self._rmqclient.open(self._results_queue) as subscription:
            while self.has_pending_commands():
                log.debug("Waiting for responses to be returned by the agent. "
                          "%i total responses remain", len(self._pending_list))
                msg = subscription.get_message()
                msg.ack()
                msg_id = msg.id.lower()
                item, index = muranoconductor.helpers.find(
                    lambda t: t['id'] == msg_id, self._pending_list)
                if item:
                    self._pending_list.pop(index)
                    item['callback'](msg.body)

        return True
