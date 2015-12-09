# -*- coding: utf-8 -*-

#
#
#  Copyright 2014 Netflix, Inc.
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
aminator.plugins.blockdevice.null
==================================
null block device manager
"""
import logging

from aminator.plugins.blockdevice.base import BaseBlockDevicePlugin

__all__ = ('NullBlockDevicePlugin',)
log = logging.getLogger(__name__)


class NullBlockDevicePlugin(BaseBlockDevicePlugin):
    _name = 'null'

    def __enter__(self):
        return '/dev/null'

    def __exit__(self, typ, val, trc):
        if typ:
            log.debug('Exception encountered in Null block device plugin',
                      exc_info=(typ, val, trc))
        return False
