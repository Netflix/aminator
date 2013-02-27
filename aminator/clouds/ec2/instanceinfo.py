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

from aminator.clouds.ec2.core import ec2connection, is_ec2_instance
from aminator.utils import native_device_prefix, native_block_device, device_prefix


log = logging.getLogger(__name__)


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
        if device_prefix(self.block_device_mapping.keys()[0]) != native_device_prefix():
            self._blockdevs2native()
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

    def _blockdevs2native(self):
        """Amazon reports old-style device nodes regardless of how the OS sees them.
        This method creates a block device mapping using device names that the OS will
        recognize."""
        new_map = dict()
        for dev in self.block_device_mapping:
            new_map[native_block_device(dev)] = self.block_device_mapping[dev]
        self.block_device_mapping = new_map


this_instance = InstanceInfo()
