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
import yaml

log = logging.getLogger(__name__)


class Environment(object):
    """ The environment and orchetrator for amination """
    # TODO: given that this represents a workflow, this should possibly be an entry point

    def _attach_plugins(self):
        log.debug('Attaching plugins to environment {0}'.format(self._name))
        env_config = self._config.environments[self._name]
        for kind, name in env_config.iteritems():
            log.debug('Attaching plugin {0} for {1}'.format(name, kind))
            plugin = self._plugin_manager.find_by_kind(kind, name)
            setattr(self, kind, plugin.obj)
            log.debug('Attached: {0}'.format(getattr(self, kind)))

        kind = "metrics"
        if not getattr(self, kind, None):
            name = self._config.environments.get(kind, "logger")
            plugin = self._plugin_manager.find_by_kind(kind, name)
            setattr(self, kind, plugin.obj)

        log.debug("============= BEGIN YAML representation of loaded configs ===============")
        log.debug(yaml.dump(self._config))
        log.debug("============== END YAML representation of loaded configs ================")

    def provision(self):
        log.info('Beginning amination! Package: {0}'.format(self._config.context.package.arg))
        with self.metrics:  # pylint: disable=no-member
            with self.cloud as cloud:  # pylint: disable=no-member
                with self.finalizer(cloud) as finalizer:  # pylint: disable=no-member
                    with self.volume(self.cloud, self.blockdevice) as volume:  # pylint: disable=no-member
                        with self.distro(volume) as distro:  # pylint: disable=no-member
                            success = self.provisioner(distro).provision()  # pylint: disable=no-member
                            if not success:
                                log.critical('Provisioning failed!')
                                return False
                        success = finalizer.finalize()
                        if not success:
                            log.critical('Finalizing failed!')
                            return False
        return True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, trc):
        if exc_type:
            log.debug('Exception encountered in environment context manager', exc_info=(exc_type, exc_value, trc))
        return False

    def __call__(self, config, plugin_manager):
        self._config = config
        self._plugin_manager = plugin_manager
        self._name = self._config.context.get('environment', self._config.environments.default)
        self._config.context['environment'] = self._name
        self._attach_plugins()
        return self
