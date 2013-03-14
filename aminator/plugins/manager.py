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
    """ Base plugin manager that all managers should inherit from """
    __metaclass__ = abc.ABCMeta

    def __init__(self, check_func=lambda x: True, invoke_on_load=True,
                 invoke_args=(), invoke_kwds={}):
        super(BasePluginManager, self).__init__(namespace=self.entry_point,
                                                check_func=check_func,
                                                invoke_on_load=invoke_on_load,
                                                invoke_args=invoke_args,
                                                invoke_kwds=invoke_kwds)

    @abc.abstractproperty
    def entry_point(self):
        return self._entry_point

    @staticmethod
    @abc.abstractmethod
    def check_func(plugin):
        """ determine whether a given plugin should be enabled """
        return True
