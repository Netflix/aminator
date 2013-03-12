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
aminator.environment
====================
A proxy into clouds, devices, etc
"""
import logging


log = logging.getLogger(__name__)


class Environment(object):
    def __init__(self, config, plugins):
        self.config = config
        self.plugins = plugins
        self.name = self.config.environment

    def provision(self):
        with self.volume_manager(self.device_manager) as volume:
            with self.provisioner as provisioner:
                error = provisioner(volume)
                if error:
                    return error
        error = self.finalizer()
        if error:
            return error
        return None

    def __enter__(self):
        self.cloud = self.plugins.cloud
        self.device_manager = self.plugins.device_manager
        self.volume_manager = self.plugins.volume_manager
        self.provisioner = self.plugins.provisioner
        self.finalizer = self.plugins.finalizer
        return self

    def __exit__(self, exc_type, exc_value, trc):
        pass
