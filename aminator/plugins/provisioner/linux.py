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
aminator.plugins.provisioner.base_linux_provisioner
===================================================
Simple base class for cases where there are small distro-specific corner cases
"""
import abc
import logging
import os

from aminator.exceptions import ProvisionException, VolumeException
from aminator.plugins.provisioner.base import BaseProvisionerPlugin
from aminator.util.linux import Chroot, lifo_mounts, mount, mounted, MountSpec, unmount
from aminator.util.linux import install_provision_configs, remove_provision_configs
from aminator.util.linux import short_circuit_files, rewire_files

__all__ = ('BaseLinuxProvisionerPlugin',)
log = logging.getLogger(__name__)


class BaseLinuxProvisionerPlugin(BaseProvisionerPlugin):
    """
    Most of what goes on between apt and yum provisioning is the same, so we factored that out,
    leaving the differences in the actual implementations
    """
    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def _refresh_package_metadata(self):
        """ subclasses must implement package metadata refresh logic """

    @abc.abstractmethod
    def _provision_package(self):
        """ subclasses must implement package provisioning logic """

    def __init__(self, *args, **kwargs):
        super(BaseLinuxProvisionerPlugin, self).__init__(*args, **kwargs)

    @property
    def enabled(self):
        return super(BaseLinuxProvisionerPlugin, self).enabled

    @enabled.setter
    def enabled(self, enable):
        super(BaseLinuxProvisionerPlugin, self).enabled = enable

    @property
    def entry_point(self):
        return super(BaseLinuxProvisionerPlugin, self).entry_point

    @property
    def name(self):
        return super(BaseLinuxProvisionerPlugin, self).name

    @property
    def full_name(self):
        return super(BaseLinuxProvisionerPlugin, self).full_name

    def configure(self, config, parser):
        super(BaseLinuxProvisionerPlugin, self).configure(config, parser)

    def add_plugin_args(self, *args, **kwargs):
        super(BaseLinuxProvisionerPlugin, self).add_plugin_args(*args, **kwargs)

    def load_plugin_config(self, *args, **kwargs):
        super(BaseLinuxProvisionerPlugin, self).load_plugin_config(*args, **kwargs)

    def provision(self):
        log.debug('Entering chroot at {0}'.format(self.mountpoint))
        config = self.config.plugins[self.full_name]
        context = self.config.context

        with Chroot(self.mountpoint):
            log.debug('Inside chroot')

            if config.get('short_circuit', False):
                if not self._short_circuit():
                    raise ProvisionException('Failure short-circuiting files')

            result = self._refresh_package_metadata()
            if not result.success:
                raise ProvisionException('Package metadata refresh failed: {0.std_err}'.format(result.result))

            result = self._provision_package()
            if not result.success:
                raise ProvisionException('Installation of {0} failed: {1.std_err}'.format(context.package.arg,
                                                                                          result.result))
        log.debug('Exited chroot')

    def _short_circuit(self):
        config = self.config.plugins[self.full_name]
        files = config.get('short_circuit_files', [])
        if files:
            if not short_circuit_files(files):
                log.critical('Unable to short circuit {0} to {1}')
                return False
            else:
                log.debug('Files short-circuited successfully')
                return True
        else:
            log.debug('No short circuit files configured')
            return True

    def _rewire(self):
        config = self.config.plugins[self.full_name]
        files = config.get('short_circuit_files', [])
        if files:
            if not rewire_files(files):
                log.critical('Unable to rewire {0} to {1}')
                return False
            else:
                log.debug('Files rewired successfully')
                return True
        else:
            log.debug('No short circuit files configured, no rewiring done')
        return True

    def configure_chroot(self):
        config = self.config.plugins[self.full_name]
        log.debug('Configuring chroot at {0}'.format(self.mountpoint))
        if config.get('configure_mounts', True):
            if not self._configure_chroot_mounts():
                log.critical('Configuration of chroot mounts failed')
                return False
        if config.get('provision_configs', True):
            if not self._install_provision_configs():
                log.critical('Installation of provisioning config failed')
                return False
        if config.get('short_circuit', True):
            if not self._short_circuit():
                log.critical('Failure during short circuiting commands')
                return False
        log.debug('Chroot environment ready')
        return True

    def _configure_chroot_mounts(self):
        config = self.config.plugins[self.full_name]
        for mountdef in config.chroot_mounts:
            dev, fstype, mountpoint, options = mountdef
            mountspec = MountSpec(dev, fstype, os.path.join(self.mountpoint, mountpoint.lstrip('/')), options)
            log.debug('Attempting to mount {0}'.format(mountspec))
            if not mounted(mountspec.mountpoint):
                result = mount(mountspec)
                if not result.success:
                    log.critical('Unable to configure chroot: {0.std_err}'.format(result))
                    return False
        else:
            log.debug('Mounts configured')
            return True

    def _install_provision_configs(self):
        config = self.config.plugins[self.full_name]
        files = config.get('provision_config_files', [])
        if files:
            if not install_provision_configs(files, self.mountpoint):
                log.critical('Error installing provisioning configs')
                return False
            else:
                log.debug('Provision config files successfully installed')
                return True
        else:
            log.debug('No provision config files configured')
            return True

    def teardown_chroot(self):
        config = self.config.plugins[self.full_name]
        log.debug('Tearing down chroot at {0}'.format(self.mountpoint))
        if config.get('short_circuit', True):
            if not self._rewire():
                log.critical('Failure during rewiring commands')
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
        config = self.config.plugins[self.full_name]
        for mountdef in reversed(config.chroot_mounts):
            dev, fstype, mountpoint, options = mountdef
            mountspec = MountSpec(dev, fstype, os.path.join(self.mountpoint, mountpoint.lstrip('/')), options)
            log.debug('Attempting to unmount {0}'.format(mountspec))
            if not mounted(mountspec.mountpoint):
                log.warn('{0} not mounted'.format(mountspec.mountpoint))
                continue
            result = unmount(mountspec.mountpoint)
            if not result.success:
                log.error('Unable to unmount {0.mountpoint}: {1.stderr}'.format(mountspec, result))
                return False
        log.debug('Checking for stray mounts')
        for mountpoint in lifo_mounts(self.mountpoint):
            log.debug('Stray mount found: {0}, attempting to unmount'.format(mountpoint))
            result = unmount(mountpoint)
            if not result.success:
                log.error('Unable to unmount {0.mountpoint}: {1.stderr}'.format(mountspec, result))
                return False

    def _remove_provision_configs(self):
        config = self.config.plugins[self.full_name]
        files = config.get('provision_config_files', [])
        if files:
            if not remove_provision_configs(files, self.mountpoint):
                log.critical('Error removing provisioning configs')
                return False
            else:
                log.debug('Provision config files successfully removed')
                return True
        else:
            log.debug('No provision config files configured')
            return True

    def __enter__(self):
        if not self.configure_chroot():
            raise VolumeException('Error configuring chroot')
        return self

    def __exit__(self, exc_type, exc_value, trace):
        if not self.teardown_chroot():
            raise VolumeException('Error tearing down chroot')
        return False

    def __call__(self, volume):
        self.mountpoint = volume
        return self