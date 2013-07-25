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
aminator.plugins.provisioner.linux
==================================
Simple base class for cases where there are small distro-specific corner cases
"""
import abc
import logging
import os
import shutil

from glob import glob

from aminator.exceptions import VolumeException
from aminator.plugins.provisioner.base import BaseProvisionerPlugin
from aminator.util import download_file
from aminator.util.linux import Chroot, lifo_mounts, mount, mounted, MountSpec, unmount, command
from aminator.util.linux import install_provision_configs, remove_provision_configs


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

    @abc.abstractmethod
    def _store_package_metadata(self):
        """ stuff name, version, release into context """

    @abc.abstractmethod
    def _activate_provisioning_service_block(self):
        """ enable service startup after we're done installing packages in chroot"""

    @abc.abstractmethod
    def _deactivate_provisioning_service_block(self):
        """ prevent service startup when packages are installed in chroot """

    def _pre_chroot_block(self):
        """ run commands after mounting the volume, but before chroot'ing """
        pass

    def _post_chroot_block(self):
        """ commands to run after the exiting the chroot, but before unmounting / finalizing """
        pass

    def provision(self):
        context = self._config.context

        if self._local_install():
            log.info('performing a local install of {0}'.format(context.package.arg))
            context.package.local_install = True
            if not self._stage_pkg():
                log.critical('failed to stage {0}'.format(context.package.arg))
                return False
        else:
            log.info('performing a repo install of {0}'.format(context.package.arg))
            context.package.local_install = False

        log.debug('Pre chroot command block')
        self._pre_chroot_block()

        log.debug('Entering chroot at {0}'.format(self._mountpoint))

        with Chroot(self._mountpoint):
            log.debug('Inside chroot')

            result = self._refresh_package_metadata()
            if not result.success:
                log.critical('Package metadata refresh failed: {0.std_err}'.format(result.result))
                return False

            result = self._provision_package()
            if not result.success:
                log.critical('Installation of {0} failed: {1.std_err}'.format(context.package.arg, result.result))
                return False
            self._store_package_metadata()
            if context.package.local_install and not context.package.get('preserve', False):
                os.remove(context.package.arg)

            # run scripts that may have been delivered in the package
            scripts_dir = self._config.plugins[self.full_name].get('scripts_dir', '/var/local')
            log.debug('scripts_dir = {0}'.format(scripts_dir))

            if scripts_dir:
                self._run_provision_scripts(scripts_dir)

        log.debug('Exited chroot')

        log.debug('Post chroot command block')
        self._post_chroot_block()

        log.info('Provisioning succeeded!')
        return True

    def _run_provision_scripts(self, scripts_dir):
        """
        execute every python or shell script found in scripts_dir
            1. run python scripts in lexical order
            2. run shell scripts in lexical order

        :param scripts_dir: path in chroot to look for python and shell scripts
        :return: None
        """

        python_script_files = sorted(glob(scripts_dir + '/*.py'))
        if python_script_files is None:
            log.debug('no python scripts found in {0}'.format(scripts_dir))
        else:
            log.debug('found python script {0} in {1}'.format(python_script_files, scripts_dir))
            for script in python_script_files:
                log.debug('executing python {0}'.format(script))
                run_script('python {0}'.format(script))

        shell_script_files = sorted(glob(scripts_dir + '/*.sh'))
        if shell_script_files is None:
            log.debug('no shell scripts found in {0}'.format(scripts_dir))
        else:
            log.debug('found shell script {0} in {1}'.format(shell_script_files, scripts_dir))
            for script in python_script_files:
                log.debug('executing sh {0}'.format(script))
                run_script('sh {0}'.format(script))

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

        #TODO: kvick we should rename 'short_circuit' to something like 'disable_service_start'
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

    def _local_install(self):
        """True if context.package.arg ends with a package extension
        """
        config = self._config
        ext = config.plugins[self.full_name].get('pkg_extension', '')
        if not ext:
            return False

        # ensure extension begins with a dot
        ext = '.{0}'.format(ext.lstrip('.'))

        return config.context.package.arg.endswith(ext)

    def _stage_pkg(self):
        """copy package file into AMI volume.
        """
        context = self._config.context
        context.package.file = os.path.basename(context.package.arg)
        context.package.full_path = os.path.join(self._mountpoint,
                                                 context.package.dir.lstrip('/'),
                                                 context.package.file)
        try:
            if any(protocol in context.package.arg for protocol in ['http://', 'https://']):
                self._download_pkg(context)
            else:
                self._move_pkg(context)
        except Exception:
            log.exception('Error encountered while staging package')
            return False
            # reset to chrooted file path
        context.package.arg = os.path.join(context.package.dir, context.package.file)
        return True

    def _download_pkg(self, context):
        """dowload url to context.package.dir
        """
        pkg_url = context.package.arg
        dst_file_path = context.package.full_path
        log.debug('downloading {0} to {1}'.format(pkg_url, dst_file_path))
        download_file(pkg_url, dst_file_path, context.package.get('timeout', 1),
                      verify_https=context.get('verify_https', False))

    def _move_pkg(self, context):
        src_file = context.package.arg.replace('file://', '')
        dst_file_path = context.package.full_path
        shutil.move(src_file, dst_file_path)

    def __enter__(self):
        if not self._configure_chroot():
            raise VolumeException('Error configuring chroot')
        return self

    def __exit__(self, exc_type, exc_value, trace):
        if exc_type and self._config.context.preserve_on_error:
            return False
        if not self._teardown_chroot():
            raise VolumeException('Error tearing down chroot')
        return False

    def __call__(self, mountpoint):
        self._mountpoint = mountpoint
        return self

@command()
def run_script(script):
    return '{0}'.format(script)
