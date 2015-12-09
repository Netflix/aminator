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
aminator.plugins.finalizer.base
===============================
Base class(es) for finalizer plugins
"""
import abc
import logging

from aminator.plugins.base import BasePlugin


__all__ = ('BaseFinalizerPlugin',)
log = logging.getLogger(__name__)


class BaseFinalizerPlugin(BasePlugin):
    """
    Finalizers handle administrivia post-package-provisioning. Think: registration, tagging, snapshotting, etc.
    They are context managers to ensure resource cleanup
    """

    __metaclass__ = abc.ABCMeta
    _entry_point = 'aminator.plugins.finalizer'

    @abc.abstractmethod
    def finalize(self):
        """ finalize an image """

    def __enter__(self):
        return self

    def __exit__(self, typ, val, trc):
        if typ:
            log.debug('Exception encountered in Finalizer plugin context manager',
                      exc_info=(typ, val, trc))
        return False

    def __call__(self, cloud):
        self._cloud = cloud
