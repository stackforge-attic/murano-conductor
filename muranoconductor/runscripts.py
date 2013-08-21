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

import types
import os.path
from subprocess import call
import xml_code_engine


def _instance_names_func(environment, hostNames):
    return ['e{0}.{1}'.format(environment, item) for item in hostNames]

def _flat(arguments):
    if not isinstance(arguments, types.ListType):
        return arguments
    else:
        result = []
        for item in arguments:
            result.append(_flat(item))
        return result

def _run_script_func(name, arguments, **kwargs):
    if not isinstance(arguments, types.ListType):
        arguments = [arguments]

    name = os.path.normpath("data/scripts/" + name)
    call([name] + _flat(arguments))


xml_code_engine.XmlCodeEngine.register_function(
    _run_script_func, "run-script")

xml_code_engine.XmlCodeEngine.register_function(
    _instance_names_func, "instance-names")
