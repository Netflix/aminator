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
    __metaclass__ = abc.ABCMeta
    _entry_point = 'aminator.plugins.cloud'

    @abc.abstractmethod
    def __init__(self, *args, **kwargs):
        self._connection = None
        super(BaseCloudPlugin, self).__init__(*args, **kwargs)

    @abc.abstractproperty
    def enabled(self):
        return super(BaseCloudPlugin, self).enabled

    @enabled.setter
    def enabled(self, enable):
        super(BaseCloudPlugin, self).enabled = enable

    @abc.abstractproperty
    def entry_point(self):
        return super(BaseCloudPlugin, self).entry_point

    @abc.abstractproperty
    def name(self):
        return super(BaseCloudPlugin, self).name

    @abc.abstractproperty
    def full_name(self):
        return super(BaseCloudPlugin, self).full_name

    @abc.abstractmethod
    def configure(self, config, parser):
        super(BaseCloudPlugin, self).configure(config, parser)

    @abc.abstractmethod
    def add_plugin_args(self, *args, **kwargs):
        super(BaseCloudPlugin, self).add_plugin_args(*args, **kwargs)

    @abc.abstractmethod
    def load_plugin_config(self, *args, **kwargs):
        super(BaseCloudPlugin, self).load_plugin_config(*args, **kwargs)

    @abc.abstractmethod
    def connect(self, *args, **kwargs):
        """ Instructs a cloud provider to establish a connection """

    @abc.abstractmethod
    def attach_volume(self, *args, **kwargs):
        """ Instructs the cloud provider to attach some sort of volume to the instance on a given block device """

    @abc.abstractmethod
    def detach_volume(self, *args, **kwargs):
        """ Instructs the cloud provider to detach a given volume from the instance """

    @abc.abstractmethod
    def register_image(self, *args, **kwargs):
        """ Instructs the cloud provider to register a finalized image for launching """

    @abc.abstractmethod
    def is_stale_attachment(self, *args, **kwargs):
        """ checks to see if a given device is a stale attachment """

    @abc.abstractmethod
    def __enter__(self):
        """
        Cloud plugins are context managers
        """

    @abc.abstractmethod
    def __exit__(self, exc_type, exc_value, trace):
        """
        exit point for cloud context
        """