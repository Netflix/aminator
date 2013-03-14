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
The orchestrator
"""
import logging


log = logging.getLogger(__name__)


class Environment(object):
    """ The environment and orchetrator for amination """
    # TODO: given that this represents a workflow, this should possibly be an entry point

    def __init__(self, config, plugin_manager):
        self.config = config
        self.plugin_manager = plugin_manager
        self.name = self.config.get('environment', self.config.default_environment)

    def provision(self):
        with self.volume(self.blockdevice, self.cloud) as volume:
            with self.provisioner(volume) as provisioner:
                error = provisioner.provision()
                if error:
                    return error
        error = self.finalizer()
        if error:
            return error
        return None

    def __enter__(self):
        env = self.config.environments[self.name]
        cloud_plugin_name = env.cloud
        blockdevice_plugin_name = env.blockdevice
        volume_plugin_name = env.volume
        provisioner_plugin_name = env.provisioner
        finalizer_plugin_name = env.finalizer

        self.cloud = self.plugins.find_by_kind('cloud', cloud_plugin_name)
        self.blockdevice = self.plugins.find_by_kind('blockdevice', blockdevice_plugin_name)
        self.volume = self.plugins.by_kind('volume', volume_plugin_name)
        self.provisioner = self.plugins.find_by_kind('provisioner', provisioner_plugin_name)
        self.finalizer = self.plugins.find_by_kind('finalizer', finalizer_plugin_name)
        return self

    def __exit__(self, exc_type, exc_value, trc):
        pass
