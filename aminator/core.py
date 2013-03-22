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
aminator.core
=============
aminator core amination logic
"""
import logging

from aminator.config import init_defaults, log_per_package
from aminator.environment import Environment
from aminator.plugins import PluginManager

__all__ = ('Aminator', )
log = logging.getLogger(__name__)


class Aminator(object):
    def __init__(self, config=None, parser=None, plugin_manager=PluginManager, environment=Environment, debug=False):
        log.info('Aminator starting...')
        if not all((config, parser)):
            log.debug('Loading default configuration')
            config, parser = init_defaults(debug=debug)
        self.config = config
        self.parser = parser
        log.debug('Configuration loaded')
        self.plugin_manager = plugin_manager(self.config, self.parser)
        log.debug('Plugins loaded')
        self.parser.parse_args()
        log.debug('Args parsed')

        if self.config.logging.per_package.enabled:
            log.info('Configuring per-package logging')
            log_per_package(self.config, 'per_package')

        self.environment = environment()

    def aminate(self):
        with self.environment(self.config, self.plugin_manager) as env:
            error = env.provision()
            if not error:
                log.info('Amination complete!')
        return error
