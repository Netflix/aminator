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

from aminator.config import conf_action
from aminator.exceptions import DeviceException
from aminator.plugins.blockdevice.base import BaseBlockDevicePlugin
from aminator.util.linux import flock, locked, native_device_prefix
from aminator.util.metrics import raises

__all__ = ('LinuxBlockDevicePlugin',)
log = logging.getLogger(__name__)


BlockDevice = namedtuple('BlockDevice', 'node handle')


class LinuxBlockDevicePlugin(BaseBlockDevicePlugin):
    _name = 'linux'

    def configure(self, config, parser):
        super(LinuxBlockDevicePlugin, self).configure(config, parser)

        if self._config.lock_dir.startswith(('/', '~')):
            self._lock_dir = os.path.expanduser(self._config.lock_dir)
        else:
            self._lock_dir = os.path.join(self._config.aminator_root, self._config.lock_dir)

        self._lock_file = self.__class__.__name__

        self._allowed_devices = None
        self._device_prefix = None

    def add_plugin_args(self, *args, **kwargs):
        context = self._config.context
        bd_group_desc = 'Block device allocator configuration'
        blockdevice = self._parser.add_argument_group(title='Blockdevice',
                                                      description=bd_group_desc)
        blockdevice.add_argument("--block-device", dest='block_device',
                                 action=conf_action(config=context.ami),
                                 help='Block device path to use')
        blockdevice.add_argument("--partition", dest='partition',
                                 action=conf_action(config=context.ami),
                                 help='Parition number containing the root file system.')

    def __enter__(self):
        self._dev = self.allocate_dev()
        return self._dev.node

    def __exit__(self, typ, val, trc):
        if typ:
            log.debug('Exception encountered in Linux block device plugin context manager',
                      exc_info=(typ, val, trc))
        self.release_dev(self._dev)
        return False

    def _setup_allowed_devices(self):
        if all((self._device_prefix, self._allowed_devices)):
            return

        block_config = self._config.plugins[self.full_name]
        majors = block_config.device_letters

        self._device_prefix = native_device_prefix(block_config.device_prefixes)

        context = self._config.context

        if 'partition' in context.ami:
            block_config.use_minor_device_numbers = False
            self.partition = context.ami.partition

        if block_config.use_minor_device_numbers:
            device_format = '/dev/{0}{1}{2}'
            self._allowed_devices = [device_format.format(self._device_prefix, major, minor)
                                     for major in majors
                                     for minor in xrange(1, 16)]
        else:
            device_format = '/dev/{0}{1}'
            self._allowed_devices = [device_format.format(self._device_prefix, major)
                                     for major in majors]

    def allocate_dev(self):
        context = self._config.context
        if "block_device" in context.ami:
            return BlockDevice(context.ami.block_device, None)

        with flock(self._lock_file):
            return self.find_available_dev()

    def release_dev(self, dev):
        if dev.handle:
            fcntl.flock(dev.handle, fcntl.LOCK_UN)
            dev.handle.close()

    @raises("aminator.blockdevice.linux.find_available_dev.error")
    def find_available_dev(self):
        log.info('Searching for an available block device')
        self._setup_allowed_devices()
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
        raise DeviceException('Exhausted all devices, none free')
