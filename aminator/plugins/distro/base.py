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
aminator.plugins.distro.base
=================================
Base class(es) for OS distributions plugins
"""
import abc
import logging

from aminator.plugins.base import BasePlugin
from aminator.util.linux import short_circuit_files, rewire_files

__all__ = ('BaseDistroPlugin',)
log = logging.getLogger(__name__)


class BaseDistroPlugin(BasePlugin):
    """
    Distribution plugins take a volume and prepare it for provisioning.
    They are context managers to ensure resource cleanup
    """

    __metaclass__ = abc.ABCMeta
    _entry_point = 'aminator.plugins.distro'

    @abc.abstractmethod
    def __enter__(self):
        return self

    @abc.abstractmethod
    def __exit__(self, exc_type, exc_value, trace):
        if exc_type: log.exception("Exception: {0}: {1}".format(exc_type.__name__,exc_value))
        return False

    def __call__(self, mountpoint):
        self._mountpoint = mountpoint
        return self

    def _deactivate_provisioning_service_block(self):
        """
        Prevent packages installing the chroot from starting
        For RHEL-like systems, we can use short_circuit which replaces the service call with /bin/true
        """
        config = self._config.plugins[self.full_name]
        files = config.get('short_circuit_files', [])
        if files:
            if not short_circuit_files(self._mountpoint, files):
                log.critical('Unable to short circuit {0} to {1}')
                return False
            else:
                log.debug('Files short-circuited successfully')
                return True
        else:
            log.debug('No short circuit files configured')
            return True

    def _activate_provisioning_service_block(self):
        """
        Enable service startup so that things work when the AMI starts
        For RHEL-like systems, we undo the short_circuit
        """
        config = self._config.plugins[self.full_name]
        files = config.get('short_circuit_files', [])
        if files:
            if not rewire_files(self._mountpoint, files):
                log.critical('Unable to rewire {0} to {1}')
                return False
            else:
                log.debug('Files rewired successfully')
                return True
        else:
            log.debug('No short circuit files configured, no rewiring done')
        return True
