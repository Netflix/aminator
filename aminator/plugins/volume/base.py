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
    __metaclass__ = abc.ABCMeta
    _entry_point = 'aminator.plugins.volume'

    @abc.abstractmethod
    def __init__(self, *args, **kwargs):
        super(BaseVolumePlugin, self).__init__(*args, **kwargs)

    @abc.abstractproperty
    def enabled(self):
        return super(BaseVolumePlugin, self).enabled

    @enabled.setter
    def enabled(self, enable):
        super(BaseVolumePlugin, self).enabled = enable

    @abc.abstractproperty
    def entry_point(self):
        return super(BaseVolumePlugin, self).entry_point

    @abc.abstractproperty
    def name(self):
        return super(BaseVolumePlugin, self).name

    @abc.abstractproperty
    def full_name(self):
        return super(BaseVolumePlugin, self).full_name

    @abc.abstractmethod
    def configure(self, config, parser, *args, **kwargs):
        super(BaseVolumePlugin, self).configure(config, parser, *args, **kwargs)

    @abc.abstractmethod
    def add_plugin_args(self, *args, **kwargs):
        super(BaseVolumePlugin, self).add_plugin_args(*args, **kwargs)

    @abc.abstractmethod
    def load_plugin_config(self, *args, **kwargs):
        super(BaseVolumePlugin, self).load_plugin_config(*args, **kwargs)

    @abc.abstractmethod
    def __enter__(self):
        """
        Volume plugins are context managers
        __enter__ should return a volume object or identifier
        """

    @abc.abstractmethod
    def __exit__(self, exc_type, exc_value, trace):
        """
        exit point for volume context
        cleanup locks, detach volumes, recycle, etc
        """

    @abc.abstractmethod
    def __call__(self, *args, **kwargs):
        """
        The volume manager, in most all cases, will receive a set of arguments when used as a context manager
        """