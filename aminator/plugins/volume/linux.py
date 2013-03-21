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

__all__ = ('LinuxVolumePlugin',)
log = logging.getLogger(__name__)


class LinuxVolumePlugin(BaseVolumePlugin):
    _name = 'linux'

    def __init__(self, *args, **kwargs):
        super(LinuxVolumePlugin, self).__init__(*args, **kwargs)

    @property
    def enabled(self):
        return super(LinuxVolumePlugin, self).enabled

    @enabled.setter
    def enabled(self, enable):
        super(LinuxVolumePlugin, self).enabled = enable

    @property
    def entry_point(self):
        return super(LinuxVolumePlugin, self).entry_point

    @property
    def name(self):
        return super(LinuxVolumePlugin, self).name

    @property
    def full_name(self):
        return super(LinuxVolumePlugin, self).full_name

    def configure(self, config, parser, *args, **kwargs):
        super(LinuxVolumePlugin, self).configure(config, parser, *args, **kwargs)

    def add_plugin_args(self, *args, **kwargs):
        super(LinuxVolumePlugin, self).add_plugin_args(*args, **kwargs)

    def load_plugin_config(self, *args, **kwargs):
        super(LinuxVolumePlugin, self).load_plugin_config(*args, **kwargs)

    @property
    def dev(self):
        return self._dev

    def _attach(self, blockdevice):
        with blockdevice(self.cloud) as dev:
            self._dev = dev
            self.cloud.attach_volume(dev)

    def _detach(self):
        self.cloud.detach_volume(self.dev)

    def _mount(self):
        if self.config.volume_dir.startswith(('~', '/')):
            self.volume_root = os.path.expanduser(self.config.volume_dir)
        else:
            self.volume_root = os.path.join(self.config.aminator_root, self.config.volume_dir)
        self.mountpoint = os.path.join(self.volume_root, os.path.basename(self.dev))
        if not os.path.exists(self.mountpoint):
            os.makedirs(self.mountpoint)

        if not mounted(self.mountpoint):
            mountspec = MountSpec(self.dev, None, self.mountpoint, None)
            result = mount(mountspec)
            if not result.success:
                msg = 'Unable to mount {0.dev} at {0.mountpoint}: {1}'.format(mountspec, result.result.std_err)
                log.critical(msg)
                raise VolumeException(msg)
        log.debug('Mounted {0.dev} at {0.mountpoint} successfully'.format(mountspec))

    @retry(VolumeException, tries=3, delay=1, backoff=2, logger=log)
    def _unmount(self):
        if mounted(self.mountpoint):
            if busy_mount(self.mountpoint).success:
                raise VolumeException('Unable to unmount {0} from {1}'.format(self.dev, self.mountpoint))
            result = unmount(self.mountpoint)
            if not result.success:
                raise VolumeException('Unable to unmount {0} from {1}: {2}'.format(self.dev, self.mountpoint,
                                                                                   result.result.std_err))

    def _delete(self):
        self.cloud.delete_volume()

    def __enter__(self):
        self._attach(self.blockdevice)
        self._mount()
        return self.mountpoint

    def __exit__(self, exc_type, exc_value, trace):
        self._unmount()
        self._detach()
        self._delete()
        return False

    def __call__(self, cloud, blockdevice):
        self.cloud = cloud
        self.blockdevice = blockdevice
        return self