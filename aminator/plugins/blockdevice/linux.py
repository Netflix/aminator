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
import logging

from aminator.plugins.blockdevice.base import BaseBlockDevicePlugin


__all__ = ('LinuxBlockDevicePlugin',)
log = logging.getLogger(__name__)


class LinuxBlockDevicePlugin(BaseBlockDevicePlugin):
    _name = 'linux'

    def configure(self, config, parser):
        super(LinuxBlockDevicePlugin, self).configure(config, parser)

    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_value, trace):
        pass
