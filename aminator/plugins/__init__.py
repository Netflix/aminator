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
aminator.plugins
================
plugin support for aminator

Aminator currently provides the following major plugin points:
- clouds (interfaces to cloud providers)
- block device allocators (components that reserve and provide OS devices to volume managers)
- volume managers (components that attach cloud volumes and prepare them for amination)
- provisioners (components that deploy applications into the volumes provided by volume managers)
- finalizers (components that tag and register the resultant image)

Plugins may be discovered through setuptools/distribute's entry_points mechanism
or registered by placing modules on a configurable plugin path for discovery.
"""
import logging


log = logging.getLogger(__name__)


class PluginManager(object):
    """ The plugin manager manager, if you will. Responsible for booting plugins """
    _registry = {}

    def __init__(self, config, parser, plugins=None):
        """
        config.plugins.managers is a map of entry points, their kinds, and the actual manager classes
        this populates the registry dict, mapping kind and entry_point to an actual instance of the manager
        """
        for kind, plugin_info in config.plugins.entry_points.iteritems():
            entry_point = plugin_info.entry_point
            classname = plugin_info['class']

            manager_module = __import__(entry_point + '.manager', globals=globals(), locals=locals(), fromlist=(classname,))
            manager = getattr(manager_module, classname)

            self._registry[entry_point] = manager()
            self._registry[kind] = self._registry[entry_point]

            for name, plugin in self._registry[entry_point].by_name.iteritems():
                if not plugins or plugins[entry_point.split('.')[-1]] == name:
                    plugin.obj.configure(config, parser)
                    log.debug('Loaded plugin {0}.{1}'.format(entry_point, name))

    def find_by_entry_point(self, entry_point, name):
        return self._registry[entry_point].by_name[name]

    def find_by_kind(self, kind, name):
        return self._registry[kind].by_name[name]
