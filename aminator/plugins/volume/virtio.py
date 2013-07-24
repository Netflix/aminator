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
basic virtio volume allocator
"""
import logging
from aminator.plugins.volume.linux import LinuxVolumePlugin

__all__ = ('VirtioVolumePlugin',)
log = logging.getLogger(__name__)


class VirtioVolumePlugin(LinuxVolumePlugin):
    _name = 'virtio'

    def _attach(self, blockdevice):
        with blockdevice(self._cloud) as dev:
            ### The device sent to attach has just the base device name
            ### The mount must be done using the partition number
            self._dev = self._cloud.attach_volume(dev) + "1"