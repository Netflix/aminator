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
aminator.plugins.distro.linux
==================================
Simple base class for cases where there are small distro-specific corner cases
"""
import abc
import logging
import os

from aminator.exceptions import VolumeException
from aminator.plugins.distro.base import BaseDistroPlugin
from aminator.util.linux import lifo_mounts, mount, mounted, MountSpec, unmount
from aminator.util.linux import install_provision_configs, remove_provision_configs
from aminator.util.linux import short_circuit_files, rewire_files
from aminator.util.metrics import fails, timer

__all__ = ('BaseLinuxDistroPlugin',)
log = logging.getLogger(__name__)


class BaseLinuxDistroPlugin(BaseDistroPlugin):
    """
    Most of what goes on between apt and yum provisioning is the same, so we factored that out,
    leaving the differences in the actual implementations
    """
    __metaclass__ = abc.ABCMeta

    def _activate_provisioning_service_block(self):
        """
        Enable service startup so that things work when the AMI starts
        For RHEL-like systems, we undo the short_circuit
        """
        config = self._config.plugins[self.full_name]
        files = config.get('short_circuit_files', [])
        if files:
            if not rewire_files(self._mountpoint, files):
                log.warning("Unable to rewire some files")
                return True
            else:
                log.debug('Files rewired successfully')
                return True
        else:
            log.debug('No short circuit files configured, no rewiring done')
        return True

    def _deactivate_provisioning_service_block(self):
        """
        Prevent packages installing the chroot from starting
        For RHEL-like systems, we can use short_circuit which replaces the service call with /bin/true
        """
        config = self._config.plugins[self.full_name]
        files = config.get('short_circuit_files', [])
        if files:
            if not short_circuit_files(self._mountpoint, files):
                log.warning('Unable to short circuit some files')
                return True
            else:
                log.debug('Files short-circuited successfully')
                return True
        else:
            log.debug('No short circuit files configured')
            return True

    @fails("aminator.distro.linux.configure_chroot.error")
    @timer("aminator.distro.linux.configure_chroot.duration")
    def _configure_chroot(self):
        config = self._config.plugins[self.full_name]
        log.debug('Configuring chroot at {0}'.format(self._mountpoint))
        if config.get('configure_mounts', True):
            if not self._configure_chroot_mounts():
                log.critical('Configuration of chroot mounts failed')
                return False
        if config.get('provision_configs', True):
            if not self._install_provision_configs():
                log.critical('Installation of provisioning config failed')
                return False

        log.debug("starting short_circuit ")

        # TODO: kvick we should rename 'short_circuit' to something like 'disable_service_start'
        if config.get('short_circuit', False):
            if not self._deactivate_provisioning_service_block():
                log.critical('Failure short-circuiting files')
                return False

        log.debug("finished short_circuit")

        log.debug('Chroot environment ready')
        return True

    def _configure_chroot_mounts(self):
        config = self._config.plugins[self.full_name]
        for mountdef in config.chroot_mounts:
            dev, fstype, mountpoint, options = mountdef
            mountspec = MountSpec(dev, fstype, os.path.join(self._mountpoint, mountpoint.lstrip('/')), options)
            log.debug('Attempting to mount {0}'.format(mountspec))
            if not mounted(mountspec.mountpoint):
                result = mount(mountspec)
                if not result.success:
                    log.critical('Unable to configure chroot: {0.std_err}'.format(result.result))
                    return False
        log.debug('Mounts configured')
        return True

    def _install_provision_configs(self):
        config = self._config.plugins[self.full_name]
        files = config.get('provision_config_files', [])
        if files:
            if not install_provision_configs(files, self._mountpoint):
                log.critical('Error installing provisioning configs')
                return False
            else:
                log.debug('Provision config files successfully installed')
                return True
        else:
            log.debug('No provision config files configured')
            return True

    @fails("aminator.distro.linux.teardown_chroot.error")
    @timer("aminator.distro.linux.teardown_chroot.duration")
    def _teardown_chroot(self):
        config = self._config.plugins[self.full_name]
        log.debug('Tearing down chroot at {0}'.format(self._mountpoint))
        # TODO: kvick we should rename 'short_circuit' to something like 'disable_service_start'
        if config.get('short_circuit', True):
            if not self._activate_provisioning_service_block():
                log.critical('Failure during re-enabling service startup')
                return False
        if config.get('provision_configs', True):
            if not self._remove_provision_configs():
                log.critical('Removal of provisioning config failed')
                return False
        if config.get('configure_mounts', True):
            if not self._teardown_chroot_mounts():
                log.critical('Teardown of chroot mounts failed')
                return False
        log.debug('Chroot environment cleaned')
        return True

    def _teardown_chroot_mounts(self):
        config = self._config.plugins[self.full_name]
        for mountdef in reversed(config.chroot_mounts):
            dev, fstype, mountpoint, options = mountdef
            mountspec = MountSpec(dev, fstype, os.path.join(self._mountpoint, mountpoint.lstrip('/')), options)
            log.debug('Attempting to unmount {0}'.format(mountspec))
            if not mounted(mountspec.mountpoint):
                log.warning('{0} not mounted'.format(mountspec.mountpoint))
                continue
            result = unmount(mountspec.mountpoint)
            if not result.success:
                log.error('Unable to unmount {0.mountpoint}: {1.std_err}'.format(mountspec, result.result))
                return False
        log.debug('Checking for stray mounts')
        for mountpoint in lifo_mounts(self._mountpoint):
            log.debug('Stray mount found: {0}, attempting to unmount'.format(mountpoint))
            result = unmount(mountpoint)
            if not result.success:
                log.error('Unable to unmount {0.mountpoint}: {1.std_err}'.format(mountspec, result.result))
                return False
        log.debug('Teardown of chroot mounts succeeded!')
        return True

    def _remove_provision_configs(self):
        config = self._config.plugins[self.full_name]
        files = config.get('provision_config_files', [])
        if files:
            if not remove_provision_configs(files, self._mountpoint):
                log.critical('Error removing provisioning configs')
                return False
            else:
                log.debug('Provision config files successfully removed')
                return True
        else:
            log.debug('No provision config files configured')
            return True

    def __enter__(self):
        if not self._configure_chroot():
            raise VolumeException('Error configuring chroot')
        return self

    def __exit__(self, exc_type, exc_value, trace):
        if exc_type:
            log.debug('Exception encountered in Linux distro plugin context manager',
                      exc_info=(exc_type, exc_value, trace))
        if exc_type and self._config.context.get("preserve_on_error", False):
            return False
        if not self._teardown_chroot():
            raise VolumeException('Error tearing down chroot')
        return False

    def __call__(self, mountpoint):
        self._mountpoint = mountpoint
        return self
