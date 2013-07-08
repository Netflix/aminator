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

"""
aminator.plugins.volume.virtio
=============================
basic virtio volume allocator
"""
import logging
import os
import fcntl
from aminator.exceptions import DeviceException
from aminator.plugins.blockdevice.linux import LinuxBlockDevicePlugin, BlockDevice
from aminator.util.linux import locked, native_device_prefix

__all__ = ('VirtioBlockDevicePlugin',)
log = logging.getLogger(__name__)


class VirtioBlockDevicePlugin(LinuxBlockDevicePlugin):
    _name = 'virtio'

    def configure(self, config, parser):
        super(VirtioBlockDevicePlugin, self).configure(config, parser)

        block_config = self._config.plugins[self.full_name]

        if self._config.lock_dir.startswith(('/', '~')):
            self._lock_dir = os.path.expanduser(self._config.lock_dir)
        else:
            self._lock_dir = os.path.join(self._config.aminator_root, self._config.lock_dir)

        self._lock_file = self.__class__.__name__

        majors = block_config.device_letters
        self._device_prefix = native_device_prefix(block_config.device_prefixes)
        device_format = '/dev/{0}{1}'

        self._allowed_devices = [device_format.format(self._device_prefix, major)
                                 for major in majors]



