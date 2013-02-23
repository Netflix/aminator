# -*- coding: utf-8 -*-

#
#
#  Copyright 2013 Netflix, Inc.
#
#     Licensed under the Apache License, Version 2.0 (the "License");
#     you may not use this file except in compliance with the License.
#     You may obtain a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#     Unless required by applicable law or agreed to in writing, software
#     distributed under the License is distributed on an "AS IS" BASIS,
#     WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#     See the License for the specific language governing permissions and
#     limitations under the License.
#
#

import logging

import botocore.session

log = logging.getLogger(__name__)

_ec2_operations = botocore.session.Session().get_service_data('ec2')['operations']
_ec2_data = dict((operation['name'], operation) for operation in _ec2_operations)


def _find_state_enum(dictionary, path="", search_key='State'):
    ret = None
    if isinstance(dictionary, dict):
        if search_key in dictionary:
            if search_key == 'enum':
                log.debug(path, str(dictionary[search_key]))
                return dictionary[search_key]
            else:
                return _find_state_enum(dictionary[search_key], "%s['%s']" % (path, search_key), 'enum')
        else:
            for key in dictionary:
                ret = _find_state_enum(dictionary[key], "%s['%s']" % (path, key), search_key)
                if ret is not None:
                    break
            return ret


def ec2_op_states(op):
    return _find_state_enum(_ec2_data[op])


ec2_obj_states = {'Image': ec2_op_states('DescribeImages'),
                  'Volume': ec2_op_states('DescribeVolumes'),
                  'Snapshot': ec2_op_states('DescribeSnapshots'),
                  'Instance': ec2_op_states('DescribeInstances')}

ec2_obj_states['Image'].append('pending')
ec2_obj_states['Snapshot'].append('100%')
