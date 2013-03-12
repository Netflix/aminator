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
aminator.plugins.device_manager.linux
=====================================
basic linux device manager
"""
import fcntl
import logging
import os
from contextlib import contextmanager

from aminator.clouds.ec2.utils import stale_attachment
from aminator.exceptions import DeviceError
from aminator.utils import flock, locked
from aminator.plugins.base import BaseDeviceManagerPlugin


log = logging.getLogger(__name__)


class LinuxDeviceManager(BaseDeviceManagerPlugin):
    def native_device_prefix(self):
        for prefix in self.config.device_prefixes:
            if any(device.startswith(prefix) for device in os.listdir('/sys/block')):
                return prefix
        else:
            return None

    def device_prefix(self, source_device):
        # strip off any incoming /dev/ foo
        source_device_name = os.path.basename(source_device)
        # if we have a subdevice/partition...
        if source_device_name[-1].isdigit():
            # then its prefix is the name minus the last TWO chars
            return source_device_name[:-2:]
        else:
            # otherwise, just strip the last one
            return source_device_name[:-1:]

    def native_block_device(self, source_device):
        native_prefix = self.native_device_prefix()
        source_device_prefix = self.device_prefix(source_device)
        if source_device_prefix == native_prefix:
            # we're okay, using the right name already, just return the same name
            return source_device
        else:
            # sub out the bad prefix for the good
            return source_device.replace(source_device_prefix, native_prefix)

    def allowed_devices(self):
        """
        Returns a sequence consisting of allowed device names for attaching volumes
        """
        majors = self.config.device_letters
        device_prefix = self.native_device_prefix()
        device_format = '/dev/{0}{1}{2}'

        return [device_format.format(device_prefix, major, minor) for major in majors
                for minor in xrange(1, 16)]

    def find_available_dev(self):
        """
        Iterates through allowed devices and attempts to return a free device
        To be safe, wrap this call in a flock so only one process can hunt at a
        time. Better, use the @device() context manager!

        :returns: tuple(device node, device handle)
        """
        for dev in self.allowed_devices():
            device_node_lock = os.path.join(self.config.lockdir, os.path.basename(dev))
            if os.path.exists(dev):
                log.debug('%s exists, skipping' % dev)
                continue
            if locked(device_node_lock):
                log.debug('%s is locked, skipping' % dev)
                continue
            if stale_attachment(dev):
                log.debug('%s is stale, skipping' % dev)
                continue
            fh = open(device_node_lock, 'a')
            fcntl.flock(fh, fcntl.LOCK_EX)
            log.debug('fh = {0}, dev = {1}'.format(str(fh), dev))
            return (dev, fh)
        else:
            raise DeviceError('Exhausted all devices, none free')

    @contextmanager
    def device(self):
        """
        Provides device allocation. If used in a context manager, makes best effort to identify
        an unused device node by serializing through '{lockdir}/dev_alloc' and '{lockdir}/dev'

        with device as dev:
            vol.attach(dev)
        """
        dev_alloc_lock = os.path.join(self.config.lockdir, 'dev_alloc')
        with flock(dev_alloc_lock):
            dev, dev_lock_handle = self.find_available_dev()
        yield dev
        fcntl.flock(dev_lock_handle, fcntl.LOCK_UN)
        dev_lock_handle.close()
