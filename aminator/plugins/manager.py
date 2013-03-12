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
plugin managers for finding , loading, configuring, plugging...
"""
import logging

from pkg_resources import iter_entry_points


log = logging.getLogger(__name__)


class PluginManager(object):
    def __init__(self, config, parsers):
        self.config = config
        self.parsers = parsers

    def find_plugins(self):
        pass

    def add_plugins(self, plugins=()):
        pass

    def add_plugin(self, plugin):
        pass

    def configure_plugins(self):
        pass


class EntrypointsPluginManager(PluginManager):
    pass
