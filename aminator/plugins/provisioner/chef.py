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
aminator.plugins.provisioner.chef
================================
chef provisioner
"""
import logging

from aminator.plugins.provisioner.base import BaseProvisionerPlugin
from aminator.util.linux import short_circuit_files, rewire_files

__all__ = ('ChefProvisionerPlugin',)
log = logging.getLogger(__name__)


class ChefProvisionerPlugin(BaseProvisionerPlugin):
    """
    ChefProvisionerPlugin allows you to use existing Chef recipes to manage OS and code
    """
    _name = 'chef'

    def provision(self):
        context = self._config.context
        context.package.attributes = { 'name': 'chef', 'version': '0.0.1', 'release': '0' }

        log.debug('Entering chroot at {0}'.format(self._mountpoint))

        with Chroot(self._mountpoint):
            log.debug('Inside chroot')

        log.debug('Exited chroot')
        log.info('Provisioning succeeded!')
        return True

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

        #TODO: kvick we should rename 'short_circuit' to something like 'disable_service_start'
        if config.get('short_circuit', False):
            if not self._deactivate_provisioning_service_block():
                log.critical('Failure short-circuiting files')
                return False

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
                    log.critical('Unable to configure chroot: {0.std_err}'.format(result))
                    return False
        else:
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

    def _teardown_chroot(self):
        config = self._config.plugins[self.full_name]
        log.debug('Tearing down chroot at {0}'.format(self._mountpoint))
        #TODO: kvick we should rename 'short_circuit' to something like 'disable_service_start'
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
                log.warn('{0} not mounted'.format(mountspec.mountpoint))
                continue
            result = unmount(mountspec.mountpoint)
            if not result.success:
                log.error('Unable to unmount {0.mountpoint}: {1.stderr}'.format(mountspec, result))
                return False
        log.debug('Checking for stray mounts')
        for mountpoint in lifo_mounts(self._mountpoint):
            log.debug('Stray mount found: {0}, attempting to unmount'.format(mountpoint))
            result = unmount(mountpoint)
            if not result.success:
                log.error('Unable to unmount {0.mountpoint}: {1.stderr}'.format(mountspec, result))
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

    def _download_pkg(self, context):
        """dowload url to context.package.dir
        """
        pkg_url = context.package.arg
        dst_file_path = context.package.full_path
        log.debug('downloading {0} to {1}'.format(pkg_url, dst_file_path))
        download_file(pkg_url, dst_file_path, context.package.get('timeout', 1))

    def _move_pkg(self, context):
        src_file = context.package.arg.replace('file://', '')
        dst_file_path = context.package.full_path
        shutil.move(src_file, dst_file_path)

    def __enter__(self):
        if not self._configure_chroot():
            raise VolumeException('Error configuring chroot')
        return self

    def __exit__(self, exc_type, exc_value, trace):
        if not self._teardown_chroot():
            raise VolumeException('Error tearing down chroot')
        return False

    def __call__(self, mountpoint):
        self._mountpoint = mountpoint
        return self
