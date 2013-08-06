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

import glob
import sys
import traceback

import anyjson
import eventlet
from muranoconductor.openstack.common import service
from workflow import Workflow
from commands.dispatcher import CommandDispatcher
from openstack.common import log as logging
from config import Config
import reporting
from muranocommon.messaging import MqClient, Message
from muranoconductor import config as cfg

import windows_agent
import cloud_formation

log = logging.getLogger(__name__)


class ConductorWorkflowService(service.Service):
    def __init__(self):
        super(ConductorWorkflowService, self).__init__()

    def start(self):
        super(ConductorWorkflowService, self).start()
        self.tg.add_thread(self._start_rabbitmq)

    def stop(self):
        super(ConductorWorkflowService, self).stop()

    def create_rmq_client(self):
        rabbitmq = cfg.CONF.rabbitmq
        connection_params = {
            'login': rabbitmq.login,
            'password': rabbitmq.password,
            'host': rabbitmq.host,
            'port': rabbitmq.port,
            'virtual_host': rabbitmq.virtual_host,
            'ssl': rabbitmq.ssl,
            'ca_certs': rabbitmq.ca_certs.strip() or None
        }
        return MqClient(**connection_params)

    def _start_rabbitmq(self):
        while True:
            try:
                with self.create_rmq_client() as mq:
                    mq.declare('tasks', 'tasks')
                    mq.declare('task-results')
                    with mq.open('tasks',
                                 prefetch_count=
                                 cfg.CONF.max_environments) as subscription:
                        while True:
                            msg = subscription.get_message(timeout=2)
                            if msg is not None:
                                eventlet.spawn(self._task_received, msg)
            except Exception as ex:
                log.exception(ex)

    def _task_received(self, message):
        task = message.body or {}
        message_id = message.id
        with self.create_rmq_client() as mq:
            try:
                log.info('Starting processing task {0}: {1}'.format(
                    message_id, anyjson.dumps(task)))
                reporter = reporting.Reporter(mq, message_id, task['id'])
                config = Config()

                command_dispatcher = CommandDispatcher('e' + task['id'], mq,
                                                       task['token'],
                                                       task['tenant_id'],
                                                       reporter)
                workflows = []
                for path in glob.glob("data/workflows/*.xml"):
                    log.debug('Loading XML {0}'.format(path))
                    workflow = Workflow(path, task, command_dispatcher, config,
                                        reporter)
                    workflows.append(workflow)

                stop = False
                while not stop:
                    try:
                        while True:
                            result = False
                            for workflow in workflows:
                                if workflow.execute():
                                    result = True
                            if not result:
                                log.debug(
                                    "No rules matched, "
                                    "will now execute pending commands")
                                break
                        if not command_dispatcher.execute_pending():
                            log.debug("No pending commands found, "
                                      "seems like we are done")
                            break
                        if self.check_stop_requested(task):
                            log.info("Workflow stop requested")
                            stop = True
                    except Exception as ex:
                        reporter.report_generic(
                            "Unexpected error has occurred", ex.message,
                            'error')
                        log.exception(ex)
                        break
                command_dispatcher.close()
                if stop:
                    log.info("Workflow stopped by 'stop' command")
            finally:
                self.cleanup(task, reporter)
                result_msg = Message()
                result_msg.body = task
                result_msg.id = message_id

                mq.send(message=result_msg, key='task-results')
                message.ack()
        log.info('Finished processing task {0}. Result = {1}'.format(
            message_id, anyjson.dumps(task)))

    def cleanup(self, model, reporter):
        try:
            if 'token' in model:
                del model['token']

            if 'temp' in model:
                del model['temp']

            services = model.get('services', [])
            for service in services:
                if 'temp' in service:
                    del service['temp']

                units = service.get('units', [])
                for unit in units:
                    if 'temp' in unit:
                        del unit['temp']
        except Exception as e:
            log.exception("Unexpected exception has occurred")
            if reporter:
                reporter.report_generic("Unexpected error has occurred",
                                        e.message, 'error')

    def check_stop_requested(self, model):
        if 'temp' in model:
            if '_stop_requested' in model['temp']:
                return model['temp']['_stop_requested']
        return False
