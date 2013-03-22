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
from aminator.util.linux import flock, locked, native_device_prefix


__all__ = ('LinuxBlockDevicePlugin',)
log = logging.getLogger(__name__)


BlockDevice = namedtuple('BlockDevice', 'node handle')


class LinuxBlockDevicePlugin(BaseBlockDevicePlugin):
    _name = 'linux'

    def configure(self, config, parser):
        super(LinuxBlockDevicePlugin, self).configure(config, parser)

        block_config = self._config.plugins[self.full_name]

        if self._config.lock_dir.startswith(('/', '~')):
            self._lock_dir = os.path.expanduser(self._config.lock_dir)
        else:
            self._lock_dir = os.path.join(self._config.aminator_root, self._config.lock_dir)

        self._lock_file = self.__class__.__name__

        majors = block_config.device_letters
        self._device_prefix = native_device_prefix(block_config.device_prefixes)
        device_format = '/dev/{0}{1}{2}'

        self._allowed_devices = [device_format.format(self._device_prefix, major, minor)
                                 for major in majors
                                 for minor in xrange(1, 16)]

    def __enter__(self):
        with flock(self._lock_file):
            dev = self.find_available_dev()
        self._dev = dev
        return self._dev.node

    def __exit__(self, typ, val, trc):
        fcntl.flock(self._dev.handle, fcntl.LOCK_UN)
        self._dev.handle.close()

    def find_available_dev(self):
        log.info('Searching for an available block device')
        for dev in self._allowed_devices:
            log.debug('checking if device {0} is available'.format(dev))
            device_lock = os.path.join(self._lock_dir, os.path.basename(dev))
            if os.path.exists(dev):
                log.debug('{0} exists, skipping'.format(dev))
                continue
            elif locked(device_lock):
                log.debug('{0} is locked, skipping'.format(dev))
                continue
            elif self.cloud.is_stale_attachment(dev, self._device_prefix):
                log.debug('{0} is stale, skipping'.format(dev))
                continue
            else:
                log.debug('Device {0} looks good, attempting to lock.'.format(dev))
                fh = open(device_lock, 'a')
                fcntl.flock(fh, fcntl.LOCK_EX)
                log.debug('device locked. fh = {0}, dev = {1}'.format(str(fh), dev))
                log.info('Block device {0} allocated'.format(dev))
                return BlockDevice(dev, fh)
        else:
            raise DeviceException('Exhausted all devices, none free')
