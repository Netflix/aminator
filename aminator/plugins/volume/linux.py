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
import os

from aminator.util import retry
from aminator.util.linux import MountSpec, busy_mount, mount, mounted, unmount
from aminator.exceptions import VolumeException
from aminator.plugins.volume.base import BaseVolumePlugin
from aminator.util.metrics import raises

__all__ = ('LinuxVolumePlugin',)
log = logging.getLogger(__name__)


class LinuxVolumePlugin(BaseVolumePlugin):
    _name = 'linux'

    def _attach(self, blockdevice):
        with blockdevice(self._cloud) as dev:
            self._dev = dev
            self._config.context.volume["dev"] = self._dev
            self._cloud.attach_volume(self._dev)

    def _detach(self):
        self._cloud.detach_volume(self._dev)

    @raises("aminator.volume.linux.mount.error")
    def _mount(self):
        if self._config.volume_dir.startswith(('~', '/')):
            self._volume_root = os.path.expanduser(self._config.volume_dir)
        else:
            self._volume_root = os.path.join(self._config.aminator_root, self._config.volume_dir)
        self._mountpoint = os.path.join(self._volume_root, os.path.basename(self._dev))
        if not os.path.exists(self._mountpoint):
            os.makedirs(self._mountpoint)

        if not mounted(self._mountpoint):
            # Handle optional partition
            dev = self._dev
            if self._blockdevice.partition is not None:
                dev = '{0}{1}'.format(dev, self._blockdevice.partition)

            mountspec = MountSpec(dev, None, self._mountpoint, None)

            result = mount(mountspec)
            if not result.success:
                msg = 'Unable to mount {0.dev} at {0.mountpoint}: {1}'.format(mountspec, result.result.std_err)
                log.critical(msg)
                raise VolumeException(msg)
        log.debug('Mounted {0.dev} at {0.mountpoint} successfully'.format(mountspec))

    @raises("aminator.volume.linux.umount.error")
    @retry(VolumeException, tries=6, delay=1, backoff=2, logger=log)
    def _unmount(self):
        if mounted(self._mountpoint):
            if busy_mount(self._mountpoint).success:
                raise VolumeException('Unable to unmount {0} from {1}'.format(self._dev, self._mountpoint))
            result = unmount(self._mountpoint)
            if not result.success:
                raise VolumeException('Unable to unmount {0} from {1}: {2}'.format(self._dev, self._mountpoint, result.result.std_err))

    def _delete(self):
        self._cloud.delete_volume()

    def __enter__(self):
        self._attach(self._blockdevice)
        self._mount()
        self._config.context.volume["mountpoint"] = self._mountpoint
        return self._mountpoint

    def __exit__(self, exc_type, exc_value, trace):
        if exc_type:
            log.debug('Exception encountered in linux volume plugin context manager',
                      exc_info=(exc_type, exc_value, trace))
        if exc_type and self._config.context.get("preserve_on_error", False):
            return False
        self._unmount()
        self._detach()
        self._delete()
        return False
