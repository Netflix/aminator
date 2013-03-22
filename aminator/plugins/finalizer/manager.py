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
aminator.plugins.finalizer.manager
==================================
Finalizer plugin manager(s) and utils
"""
import logging

from aminator.plugins.manager import BasePluginManager


log = logging.getLogger(__name__)


class FinalizerPluginManager(BasePluginManager):
    """ Finalizer Plugin Manager """
    _entry_point = 'aminator.plugins.finalizer'

    @property
    def entry_point(self):
        return self._entry_point
