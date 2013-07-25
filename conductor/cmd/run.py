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

import sys
import os

from conductor import config
from conductor.openstack.common import log
from conductor.openstack.common import service
from conductor.app import ConductorWorkflowService


def main():
    try:
        config.parse_args()
        os.chdir(config.CONF.data_dir)
        log.setup('conductor')
        launcher = service.ServiceLauncher()
        launcher.launch_service(ConductorWorkflowService())
        launcher.wait()
    except RuntimeError, e:
        sys.stderr.write("ERROR: %s\n" % e)
        sys.exit(1)


if __name__ == '__main__':
    main()
