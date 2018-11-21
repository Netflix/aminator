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
aminator.plugins.volume.linux
=============================
basic linux volume allocator
"""
import logging

from aminator.util.linux import resize2fs, fsck, growpart
from aminator.exceptions import VolumeException
from aminator.plugins.volume.base import BaseVolumePlugin


__all__ = ('LinuxVolumePlugin',)
log = logging.getLogger(__name__)


class LinuxVolumePlugin(BaseVolumePlugin):
    _name = 'linux'

    def _attach(self, blockdevice):
        with blockdevice(self._cloud) as dev:
            self._dev = dev
            if blockdevice.partition is not None:
                devpart = '{0}{1}'.format(dev, blockdevice.partition)
                self.context.volume['dev'] = devpart
            else:
                self.context.volume['dev'] = self._dev
            self._cloud.attach_volume(self._dev)

    def _detach(self):
        self._cloud.detach_volume(self._dev)

    def _resize(self):
        log.info('Checking and repairing root volume as necessary')
        fsck_op = fsck(self.context.volume.dev)
        if not fsck_op.success:
            raise VolumeException(
                'fsck of {} failed: {}'.format(self.context.volume.dev, fsck_op.result.std_err))
        log.info('Attempting to resize root fs to fill volume')
        if self._blockdevice.partition is not None:
            log.info('Growing partition if necessary')
            growpart_op = growpart(self._dev, self._blockdevice.partition)
            if not growpart_op.success:
                volmsg = 'growpart of {} partition {} failed: {}'
                raise VolumeException(
                    volmsg.format(
                        self._dev, self._blockdevice.partition, growpart_op.result.std_err))
        resize_op = resize2fs(self.context.volume.dev)
        if not resize_op.success:
            raise VolumeException(
                'resize of {} failed: {}'.format(self.context.volume.dev, resize_op.result.std_err))

    def _delete(self):
        self._cloud.delete_volume()

    def __enter__(self):
        self._attach(self._blockdevice)
        if self.plugin_config.get('resize_volume', False):
            self._resize()
        return self

    def __exit__(self, exc_type, exc_value, trace):
        if exc_type:
            log.debug('Exception encountered in linux volume plugin context manager',
                      exc_info=(exc_type, exc_value, trace))
        if exc_type and self._config.context.get("preserve_on_error", False):
            return False
        self._detach()
        self._delete()
        return False
