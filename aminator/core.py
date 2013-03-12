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

from aminator.config import config, argparsers, init_logging
from aminator.plugins.manager import PluginManager
from aminator.environment import Environment
from aminator.utils import root_check


__all__ = ('Aminator,')
log = logging.getLogger(__name__)


class Aminator(object):
    def __init__(self, config=config, parsers=None, plugins=PluginManager,
                 environment=Environment):
        self.config = config()

        if self.config.root_only:
            root = root_check()
            if not root:
                raise OSError(root, 'This library is configured to run only as root')

        self.parsers = parsers
        if not self.parsers:
            self.parsers = argparsers(config)
        self.parsers['main'].parse_known_args()

        init_logging(config)

        self.plugins = plugins(self.config, self.parsers)
        if self.parsers:
            self.parsers['main'].parse_args()
        self.environment = environment

    def aminate(self):
        with self.environment(self.config, self.plugins) as env:
            status = env.provision()
        return status
