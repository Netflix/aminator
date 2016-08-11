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
aminator.plugins.base
=====================
Base class(es) for plugin implementations
"""
import logging
import os

from aminator.config import PluginConfig


__all__ = ()
log = logging.getLogger(__name__)


class BasePlugin(object):
    """ Base class for plugins """
    _entry_point = None
    _name = None
    _enabled = True

    def __init__(self):
        if self._entry_point is None:
            raise AttributeError('Plugins must declare their entry point namespace in a _entry_point class attribute')
        if self._name is None:
            raise AttributeError('Plugins must declare their entry point name in a _name class attribute')

    @property
    def enabled(self):
        return self._enabled

    @enabled.setter
    def enabled(self, enable):
        self._enabled = enable

    @property
    def entry_point(self):
        return self._entry_point

    @property
    def name(self):
        return self._name

    @property
    def full_name(self):
        return '{0}.{1}'.format(self.entry_point, self.name)

    def configure(self, config, parser):
        """ Configure the plugin and contribute to command line args """
        log.debug("Configuring plugin {0} for entry point {1}".format(self.name, self.entry_point))
        self._config = config
        self._parser = parser
        self.load_plugin_config()
        if self.enabled:
            self.add_plugin_args()

    def add_plugin_args(self):
        pass

    def load_plugin_config(self):
        entry_point = self.entry_point
        name = self.name
        key = '.'.join((entry_point, name))

        if self._config.plugins.config_root.startswith('~'):
            plugin_conf_dir = os.path.expanduser(self._config.plugins.config_root)

        elif self._config.plugins.config_root.startswith('/'):
            plugin_conf_dir = self._config.plugins.config_root

        else:
            plugin_conf_dir = os.path.join(self._config.config_root, self._config.plugins.config_root)

        plugin_conf_files = (
            os.path.join(plugin_conf_dir, '.'.join((key, 'yml'))),
        )

        self._config.plugins[key] = PluginConfig.from_defaults(entry_point, name)
        self._config.plugins[key] = PluginConfig.dict_merge(self._config.plugins[key], PluginConfig.from_files(plugin_conf_files))
        # allow plugins to be disabled by configuration. Especially important in cases where command line args conflict
        self.enabled = self._config.plugins[key].get('enabled', True)
