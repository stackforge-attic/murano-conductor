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
import uuid

from oslo import messaging
from oslo.messaging import Notifier

from muranoconductor import config


TRANSPORT = None


class ReportNotifier(object):
    def __init__(self, transport):
        self._notifier = Notifier(transport, publisher_id=str(uuid.uuid4()))

    def report(self, report):
        return self._notifier.info({}, 'murano.report', report)


def notifier():
    global TRANSPORT
    if TRANSPORT is None:
        TRANSPORT = messaging.get_transport(config.CONF)

    return ReportNotifier(TRANSPORT)
