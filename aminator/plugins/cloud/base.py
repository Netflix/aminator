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
aminator.plugins.cloud.base
===========================
Base class(es) for cloud plugins
"""
import abc
import logging

from aminator.plugins.base import BasePlugin


__all__ = ('BaseCloudPlugin',)
log = logging.getLogger(__name__)


class BaseCloudPlugin(BasePlugin):
    """
    Cloud plugins are context managers to ensure cleanup. They are the interface to cloud objects and operations.
    """

    __metaclass__ = abc.ABCMeta
    _entry_point = 'aminator.plugins.cloud'

    _connection = None

    @abc.abstractmethod
    def connect(self):
        """ Store the resultant connection in the _connection class attribute """

    @abc.abstractmethod
    def allocate_base_volume(self, tag=True):
        """ create a volume object from the base/foundation volume """

    @abc.abstractmethod
    def attach_volume(self, blockdevice, tag=True):
        """ Instructs the cloud provider to attach some sort of volume to the instance """

    @abc.abstractmethod
    def detach_volume(self, blockdevice):
        """ Instructs the cloud provider to detach a given volume from the instance """

    @abc.abstractmethod
    def delete_volume(self):
        """ destroys a volume """

    @abc.abstractmethod
    def snapshot_volume(self, description=None):
        """ creates a snapshot from the attached volume """

    @abc.abstractmethod
    def is_volume_attached(self, blockdevice):
        """ volume attachment status """

    @abc.abstractmethod
    def is_stale_attachment(self, dev, prefix):
        """ checks to see if a given device is a stale attachment """

    @abc.abstractmethod
    def attached_block_devices(self, prefix):
        """
        list any block devices attached to the aminator instance.
        helps blockdevice plugins allocate an os device node
        """

    @abc.abstractmethod
    def add_tags(self, resource_type):
        """ consumes tags and applies them to objects """

    @abc.abstractmethod
    def register_image(self, *args, **kwargs):
        """ Instructs the cloud provider to register a finalized image for launching """

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, typ, val, trc):
        if typ:
            log.debug('Exception encountered in Cloud plugin context manager',
                      exc_info=(typ, val, trc))
        return False
