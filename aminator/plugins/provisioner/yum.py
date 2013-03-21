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
aminator.plugins.provisioner.yum
================================
basic yum provisioner
"""
import logging
import os

from aminator.exceptions import ProvisionException, VolumeException
from aminator.plugins.provisioner.base import BaseProvisionerPlugin
from aminator.util.linux import busy_mount, Chroot, lifo_mounts, mount, mounted, MountSpec, unmount
from aminator.util.linux import yum_clean_metadata, yum_install, short_circuit, rewire

__all__ = ('YumProvisionerPlugin',)
log = logging.getLogger(__name__)


class YumProvisionerPlugin(BaseProvisionerPlugin):
    _name = 'yum'

    def configure(self, config, parser):
        super(YumProvisionerPlugin, self).configure(config, parser)

    def provision(self):
        log.debug('Entering chroot at {0}'.format(self.mountpoint))
        config = self.config.plugins[self.full_name]
        context = self.config.context

        with Chroot(self.mountpoint):
            log.debug('Inside chroot')
            log.debug(os.listdir('/'))
            if config.get('short_circuit_sbin_service', False):
                if not short_circuit('/sbin/service'):
                    raise ProvisionException('Unable to short circuit /sbin/service')
            result = yum_clean_metadata()
            if not result.success:
                raise ProvisionException('yum clean metadata failed: {0.std_err}'.format(result))
            result = yum_install(context.package.arg)
            if not result.success:
                raise ProvisionException('Installation of {0} failed: {1.std_err}'.format(context.package.arg,
                                                                                          result))
            if config.get('short_circuit_sbin_service', False):
                if not rewire('/sbin/service'):
                    raise ProvisionException('Unable to rewire /sbin/service')
        log.debug('Exited chroot')

    def configure_chroot(self):
        log.debug('Configuring chroot at {0}'.format(self.mountpoint))
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
        log.debug('Chroot environment ready')
        return True

    def teardown_chroot(self):
        log.debug('Tearing down chroot at {0}'.format(self.mountpoint))
        if busy_mount(self.mountpoint).success:
            log.error('Unable to tear down chroot at {0}: device busy'.format(self.mountpoint))
            return False
        if not mounted(self.mountpoint):
            log.warn('{0} not mounted. Success?...'.format(self.mountpoint))
            return True

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

