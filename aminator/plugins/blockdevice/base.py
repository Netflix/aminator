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
aminator.plugins.blockdevice.base
=================================
Base class(es) for block device manager plugins
"""
import abc
import logging

from aminator.plugins.base import BasePlugin


__all__ = ('BaseBlockDevicePlugin',)
log = logging.getLogger(__name__)


class BaseBlockDevicePlugin(BasePlugin):
    """
    BlockDevicePlugins are context managers and as such, need to implement the context manager protocol
    """
    __metaclass__ = abc.ABCMeta
    _entry_point = 'aminator.plugins.blockdevice'

    def __init__(self, *args, **kwargs):
        super(BaseBlockDevicePlugin, self).__init__(*args, **kwargs)
        self.partition = None

    @abc.abstractmethod
    def __enter__(self):
        return self

    @abc.abstractmethod
    def __exit__(self, typ, val, trc):
        if typ:
            log.debug('Exception encountered in block device plugin', exc_info=(typ, val, trc))
        return False

    def __call__(self, cloud):
        """
        By default, BlockDevicePlugins are called using
        with blockdeviceplugin(cloud) as device:
            pass
        Override if need be
        """
        self.cloud = cloud
        return self
