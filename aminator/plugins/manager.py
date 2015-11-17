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
aminator.plugins.manager
========================
Base plugin manager(s) and utils
"""
import abc
import logging

from stevedore.dispatch import NameDispatchExtensionManager


log = logging.getLogger(__name__)


class BasePluginManager(NameDispatchExtensionManager):
    """
    Base plugin manager from which all managers *should* inherit
    Descendents *must* define a _entry_point class attribute
    Descendents *may* define a _check_func class attribute holding a function that determines whether a
    given plugin should or should not be enabled
    """
    __metaclass__ = abc.ABCMeta
    _entry_point = None
    _check_func = None

    def __init__(self, check_func=None, invoke_on_load=True, invoke_args=None, invoke_kwds=None):
        invoke_args = invoke_args or ()
        invoke_kwds = invoke_kwds or {}

        if self._entry_point is None:
            raise AttributeError('Plugin managers must declare their entry point in a class attribute _entry_point')

        check_func = check_func or self._check_func
        if check_func is None:
            check_func = lambda x: True

        super(BasePluginManager, self).__init__(namespace=self.entry_point, check_func=check_func, invoke_on_load=invoke_on_load, invoke_args=invoke_args, invoke_kwds=invoke_kwds)

    @property
    def entry_point(self):
        """
        Base plugins for each plugin type must set a _entry_point class attribute to the entry point they
        are responsible for
        """
        return self._entry_point
