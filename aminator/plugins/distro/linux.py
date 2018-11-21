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
import os.path

from aminator.exceptions import VolumeException
from aminator.plugins.distro.base import BaseDistroPlugin
from aminator.util import retry
from aminator.util.linux import (
    lifo_mounts, mount, mounted, MountSpec, unmount, busy_mount)
from aminator.util.linux import install_provision_configs, remove_provision_configs
from aminator.util.linux import short_circuit_files, rewire_files
from aminator.util.metrics import fails, timer, raises

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
            if not rewire_files(self.root_mountspec.mountpoint, files):
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
            if not short_circuit_files(self.root_mountspec.mountpoint, files):
                log.warning('Unable to short circuit some files')
                return True
            else:
                log.debug('Files short-circuited successfully')
                return True
        else:
            log.debug('No short circuit files configured')
            return True

    @fails("aminator.distro.linux.mount.error")
    def _mount(self, mountspec):
        if not mounted(mountspec):
            result = mount(mountspec)
            if not result.success:
                msg = 'Unable to mount {0.dev} at {0.mountpoint}: {1}'.format(mountspec, result.result.std_err)
                log.critical(msg)
                return False
        log.debug('Device {0.dev} mounted at {0.mountpoint}'.format(mountspec))
        return True

    @raises("aminator.distro.linux.umount.error")
    @retry(VolumeException, tries=10, delay=1, backoff=1, logger=log, maxdelay=1)
    def _unmount(self, mountspec):
        recursive_unmount = self.plugin_config.get('recursive_unmount', False)
        if mounted(mountspec):
            result = unmount(mountspec, recursive=recursive_unmount)
            if not result.success:
                err = 'Failed to unmount {0}: {1}'
                err = err.format(mountspec.mountpoint, result.result.std_err)
                open_files = busy_mount(mountspec.mountpoint)
                if open_files.success:
                    err = '{0}. Device has open files:\n{1}'.format(err, open_files.result.std_out)
                raise VolumeException(err)
        log.debug('Unmounted {0.mountpoint}'.format(mountspec))

    @fails("aminator.distro.linux.configure_chroot.error")
    @timer("aminator.distro.linux.configure_chroot.duration")
    def _configure_chroot(self):
        config = self.plugin_config
        log.debug('Configuring chroot at {0.mountpoint}'.format(self.root_mountspec))
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
        log.debug('Attempting to mount root volume: {0}'.format(self.root_mountspec))
        if not self._mount(self.root_mountspec):
            log.critical('Failed to mount root volume')
            return False
        if self.plugin_config.get('configure_mounts', True):
            for mountdef in self.plugin_config.chroot_mounts:
                dev, fstype, mountpoint, options = mountdef
                mountpoint = mountpoint.lstrip('/')
                mountpoint = os.path.join(self.root_mountspec.mountpoint, mountpoint)
                mountspec = MountSpec(dev, fstype, mountpoint, options)
                log.debug('Attempting to mount {0}'.format(mountspec))
                if not self._mount(mountspec):
                    log.critical('Mount failure, unable to configure chroot')
                    return False
        log.debug('Mounts configured')
        return True

    def _install_provision_configs(self):
        config = self.plugin_config
        files = config.get('provision_config_files', [])
        if files:
            if not install_provision_configs(files, self.root_mountspec.mountpoint):
                log.critical('Error installing provisioning configs')
                return False
            else:
                log.debug('Provision config files successfully installed')
                return True
        else:
            log.debug('No provision config files configured')
            return True

    def _unmount_root(self):
        try:
            self._unmount(self.root_mountspec)
        except VolumeException as ve:
            return False
        else:
            return True

    @fails("aminator.distro.linux.teardown_chroot.error")
    @timer("aminator.distro.linux.teardown_chroot.duration")
    def _teardown_chroot(self):
        log.debug('Tearing down chroot at {0.mountpoint}'.format(self.root_mountspec))
        # TODO: kvick we should rename 'short_circuit' to something like 'disable_service_start'
        if self.plugin_config.get('short_circuit', True):
            if not self._activate_provisioning_service_block():
                log.critical('Failure during re-enabling service startup')
                return False
        if self.plugin_config.get('provision_configs', True):
            if not self._remove_provision_configs():
                log.critical('Removal of provisioning config failed')
                return False
        if not self._teardown_chroot_mounts():
            log.critical('Teardown of chroot mounts failed')
            return False

        log.debug('Chroot environment cleaned')
        return True

    def _teardown_chroot_mounts(self):
        if not self.plugin_config.get('recursive_unmount', False):
            if self.plugin_config.get('configure_mounts', True):
                for mountdef in reversed(self.plugin_config.chroot_mounts):
                    dev, fstype, mountpoint, options = mountdef
                    mountpoint = mountpoint.lstrip('/')
                    mountpoint = os.path.join(self.root_mountspec.mountpoint, mountpoint)
                    mountspec = MountSpec(dev, fstype, mountpoint, options)
                    log.debug('Attempting to unmount {0.mountpoint}'.format(mountspec))
                    try:
                        self._unmount(mountspec)
                    except VolumeException as ve:
                        log.critical('Unable to unmount {0.mountpoint}'.format(mountspec))
                        return False
                log.debug('Checking for stray mounts')
                for mountpoint in lifo_mounts(self.root_mountspec.mountpoint):
                    log.debug('Stray mount found: {0}, attempting to unmount'.format(mountpoint))
                    try:
                        self._unmount(mountpoint)
                    except VolumeException as ve:
                        log.critical('Unable to unmount {0}'.format(mountpoint))
                        return False
        if not self._unmount_root():
            err = 'Unable to unmount root volume at {0.mountpoint)'
            err = err.format(self.root_mountspec)
            log.critical(err)
            return False
        log.debug('Teardown of chroot mounts succeeded!')
        return True

    def _remove_provision_configs(self):
        config = self.plugin_config
        files = config.get('provision_config_files', [])
        if files:
            if not remove_provision_configs(files, self.root_mountspec.mountpoint):
                log.critical('Error removing provisioning configs')
                return False
            else:
                log.debug('Provision config files successfully removed')
                return True
        else:
            log.debug('No provision config files configured')
            return True

    @property
    def root_mountspec(self):
        return self._root_mountspec

    def __enter__(self):
        if self._config.volume_dir.startswith(('~', '/')):
            root_base = os.path.expanduser(self._config.volume_dir)
        else:
            root_base = os.path.join(self._config.aminator_root, self._config.volume_dir)
        root_mountpoint = os.path.join(root_base, os.path.basename(self.context.volume.dev))
        self._root_mountspec = MountSpec(self.context.volume.dev, None, root_mountpoint, None)

        try:
            chroot_setup = self._configure_chroot()
        except Exception as e:
            chroot_setup = False
            log.critical('Error encountered during chroot setup. Attempting to clean up volumes.')
            self._teardown_chroot_mounts()
        if not chroot_setup:
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
