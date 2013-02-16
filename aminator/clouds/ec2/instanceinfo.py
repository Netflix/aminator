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

import boto
import boto.ec2
import boto.utils

from aminator.clouds.ec2 import ec2connection
from aminator.utils import memoize


log = logging.getLogger(__name__)


@memoize
def _is_ec2_instance():
    """
    :rtype: bool
    :return: True if the ec2 instance meta-data url is accessible, Return true, else False.
    """
    is_instance = boto.utils.get_instance_metadata(timeout=2)
    return is_instance is not None


class InstanceInfo(boto.ec2.instance.Instance):
    def __init__(self):
        self.id = None
        self.connection = ec2connection()
        if is_ec2_instance():
            self.id = boto.utils.get_instance_metadata()['instance-id']
            self.update()

    @property
    def is_instance(self):
        return self.id is not None

    @property
    def block_devs(self):
        if not self.is_instance:
            return None
        self.update()
        return self.block_device_mapping

    @property
    def az(self):
        if not self.is_instance:
            return None
        return self.placement

    @property
    def region(self):
        if not self.is_instance:
            return None
        return self.placement[:-1]

    @property
    def owner_id(self):
        if not self.is_instance:
            return None
        return boto.utils.get_instance_metadata(timeout=5)['network']['interfaces']['macs'].values()[0]['owner-id']

this_instance = InstanceInfo()
is_ec2_instance = _is_ec2_instance()
