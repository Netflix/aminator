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

    def attach_plugins(self):
        log.debug('Attaching plugins to environment {0}'.format(self.name))
        env_config = self.config.environments[self.name]
        for kind, name in env_config.iteritems():
            log.debug('Attaching plugin {0} for {1}'.format(name, kind))
            plugin = self.plugin_manager.find_by_kind(kind, name)
            setattr(self, kind, plugin.obj)
            log.debug('Attached: {0}'.format(getattr(self, kind)))

    def provision(self):
        log.info('Beginning amination! Package: {0}'.format(self.config.context.package.arg))
        with self.cloud as cloud:
            with self.finalizer(cloud) as finalizer:
                with self.volume(self.cloud, self.blockdevice) as volume:
                    with self.provisioner(volume) as provisioner:
                        success = provisioner.provision()
                        if not success:
                            log.critical('Provisioning failed!')
                            return False
                    success = finalizer.finalize(volume)
                    if not success:
                        log.critical('Finalizing failed!')
                        return False
        return None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, trc):
        return False

    def __call__(self, config, plugin_manager):
        self.config = config
        self.plugin_manager = plugin_manager
        self.name = self.config.context.get('environment', self.config.environments.default)
        self.config.context['environment'] = self.name
        self.attach_plugins()
        return self