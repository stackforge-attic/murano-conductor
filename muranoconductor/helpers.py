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

import deep
import types
import re


def transform_json(json, mappings):
    if isinstance(json, types.ListType):
        return [transform_json(t, mappings) for t in json]

    if isinstance(json, types.DictionaryType):
        result = {}
        for key, value in json.items():
            result[transform_json(key, mappings)] = \
                transform_json(value, mappings)
        return result

    elif isinstance(json, types.ListType):
        result = []
        for value in json:
            result.append(transform_json(value, mappings))
        return result

    elif isinstance(json, types.StringTypes) and json.startswith('$'):
        value = convert_macro_parameter(json[1:], mappings)
        if value is not None:
            return value

    return json


def convert_macro_parameter(macro, mappings):
    replaced = [False]

    def replace(match):
        replaced[0] = True
        return unicode(mappings.get(match.group(1)))

    result = re.sub('{(\\w+?)}', replace, macro)
    if replaced[0]:
        return result
    else:
        return mappings.get(macro)


def merge_lists(list1, list2):
    result = []
    for item in list1 + list2:
        exists = False
        for old_item in result:
            if deep.diff(item, old_item) is None:
                exists = True
                break
        if not exists:
            result.append(item)
    return result


def merge_dicts(dict1, dict2, max_levels=0):
    result = {}
    for key, value in dict1.items():
        result[key] = value
        if key in dict2:
            other_value = dict2[key]
            if type(other_value) != type(value):
                raise TypeError()
            if max_levels != 1 and isinstance(
                    other_value, types.DictionaryType):
                result[key] = merge_dicts(
                    value, other_value,
                    0 if max_levels == 0 else max_levels - 1)
            elif max_levels != 1 and isinstance(
                    other_value, types.ListType):
                result[key] = merge_lists(value, other_value)
            else:
                result[key] = other_value
    for key, value in dict2.items():
        if key not in result:
            result[key] = value
    return result


def find(f, seq):
    """Return first item in sequence where f(item) == True."""
    index = 0
    for item in seq:
        if f(item):
            return item, index
        index += 1
    return None, -1


def str2unicode(obj):
    if isinstance(obj, str):
        return unicode(obj)
    elif isinstance(obj, types.DictionaryType):
        result = {}
        for key, value in obj.items():
            result[str2unicode(key)] = str2unicode(value)
        return result
    elif isinstance(obj, types.ListType):
        return [str2unicode(t) for t in obj]
    return obj
