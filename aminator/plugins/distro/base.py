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
aminator.plugins.distro.base
=================================
Base class(es) for OS distributions plugins
"""
import abc
import logging

from aminator.plugins.base import BasePlugin

__all__ = ('BaseDistroPlugin',)
log = logging.getLogger(__name__)


class BaseDistroPlugin(BasePlugin):
    """
    Distribution plugins take a volume and prepare it for provisioning.
    They are context managers to ensure resource cleanup
    """

    __metaclass__ = abc.ABCMeta
    _entry_point = 'aminator.plugins.distro'

    @abc.abstractmethod
    def __enter__(self):
        return self

    @abc.abstractmethod
    def __exit__(self, exc_type, exc_value, trace):
        if exc_type:
            log.debug('Exception encountered in distro plugin context manager',
                      exc_info=(exc_type, exc_value, trace))
        return False

    def __call__(self, mountpoint):
        self._mountpoint = mountpoint
        return self
