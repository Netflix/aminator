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
aminator.plugins.blockdevice.linux
==================================
basic linux block device manager
"""
import fcntl
import os
import logging
from collections import namedtuple

from aminator.exceptions import DeviceException
from aminator.plugins.blockdevice.base import BaseBlockDevicePlugin
from aminator.util.linux import flock, locked, native_device_prefix, os_node_exists


__all__ = ('LinuxBlockDevicePlugin',)
log = logging.getLogger(__name__)


BlockDevice = namedtuple('BlockDevice', 'node handle')


class LinuxBlockDevicePlugin(BaseBlockDevicePlugin):
    _name = 'linux'

    def configure(self, config, parser):
        super(LinuxBlockDevicePlugin, self).configure(config, parser)

        block_config = self.config.plugins[self.full_name]

        if self.config.lock_dir.startswith(('/', '~')):
            self.lock_dir = os.path.expanduser(self.config.lock_dir)
        else:
            self.lock_dir = os.path.join(self.config.aminator_root, self.config.lock_dir)

        self.lock_file = self.__class__.__name__

        majors = block_config.device_letters
        self.device_prefix = native_device_prefix(block_config.device_prefixes)
        device_format = '/dev/{0}{1}{2}'

        self.allowed_devices = [device_format.format(self.device_prefix, major, minor)
                                for major in majors
                                for minor in xrange(1, 16)]

    @property
    def dev(self):
        return self._dev

    def __enter__(self):
        with flock(self.lock_file):
            dev = self.find_available_dev()
        self._dev = dev
        return self.dev.node

    def __exit__(self, exc_type, exc_value, trace):
        fcntl.flock(self.dev.handle, fcntl.LOCK_UN)
        self.dev.handle.close()

    def __call__(self, cloud):
        self.cloud = cloud
        return self

    def find_available_dev(self):
        for dev in self.allowed_devices:
            device_lock = os.path.join(self.lock_dir, os.path.basename(dev))
            if os.path.exists(dev):
                log.debug('%s exists, skipping' % dev)
                continue
            if locked(device_lock):
                log.debug('%s is locked, skipping' % dev)
                continue
            if self.cloud.check_stale(dev, self.device_prefix):
                log.debug('%s is stale, skipping' % dev)
                continue
            fh = open(device_lock, 'a')
            fcntl.flock(fh, fcntl.LOCK_EX)
            log.debug('fh = {0}, dev = {1}'.format(str(fh), dev))
            return BlockDevice(dev, fh)
        else:
            raise DeviceException('Exhausted all devices, none free')