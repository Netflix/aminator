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
aminator.plugins.volume.base
============================
Base class(es) for volume plugins
"""
import abc
import logging

from aminator.plugins.base import BasePlugin


__all__ = ('BaseVolumePlugin',)
log = logging.getLogger(__name__)


class BaseVolumePlugin(BasePlugin):
    """
    Volume plugins ask blockdevice for an os block device, the cloud for a volume at
    that block device, mount it, and return the mount point for the provisioner. How they go about it
    is up to the implementor.
    The are context managers to ensure they unmount and clean up resources
    """
    __metaclass__ = abc.ABCMeta
    _entry_point = 'aminator.plugins.volume'

    @abc.abstractmethod
    def __enter__(self):
        return self

    @abc.abstractmethod
    def __exit__(self, exc_type, exc_value, trace):
        if exc_type:
            log.debug('Exception encountered in volume plugin context manager',
                      exc_info=(exc_type, exc_value, trace))
        return False

    def __call__(self, cloud, blockdevice):
        self._cloud = cloud
        self._blockdevice = blockdevice
        return self
