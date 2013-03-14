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
    def attach_volume_to_instance(self, blockdevice):
        pass

    @abc.abstractmethod
    def detach_volume_from_instance(self):
        pass

    @abc.abstractmethod
    def register_image(self):
        pass
