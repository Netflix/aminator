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
aminator.plugins.provisioner.apt
================================
basic apt provisioner
"""
import logging
import os
import shutil

from aminator.exceptions import ProvisionException, VolumeException
from aminator.plugins.provisioner.base import BaseProvisionerPlugin
from aminator.util.linux import busy_mount, Chroot, lifo_mounts, mount, mounted, MountSpec, unmount
from aminator.util.linux import apt_get_update, apt_get_install

__all__ = ('AptProvisionerPlugin',)
log = logging.getLogger(__name__)


class AptProvisionerPlugin(BaseProvisionerPlugin):
    _name = 'apt'

    def __init__(self, *args, **kwargs):
        super(AptProvisionerPlugin, self).__init__(*args, **kwargs)

    @property
    def enabled(self):
        return super(AptProvisionerPlugin, self).enabled

    @enabled.setter
    def enabled(self, enable):
        super(AptProvisionerPlugin, self).enabled = enable

    @property
    def entry_point(self):
        return super(AptProvisionerPlugin, self).entry_point

    @property
    def name(self):
        return super(AptProvisionerPlugin, self).name

    @property
    def full_name(self):
        return super(AptProvisionerPlugin, self).full_name

    def configure(self, config, parser):
        super(AptProvisionerPlugin, self).configure(config, parser)

    def add_plugin_args(self, *args, **kwargs):
        super(AptProvisionerPlugin, self).add_plugin_args(*args, **kwargs)

    def load_plugin_config(self, *args, **kwargs):
        super(AptProvisionerPlugin, self).load_plugin_config(*args, **kwargs)

    def provision(self):
        log.debug('Entering chroot at {0}'.format(self.mountpoint))
        config = self.config.plugins[self.full_name]
        context = self.config.context

        with Chroot(self.mountpoint):
            log.debug('Inside chroot')
            log.debug(os.listdir('/'))
            result = apt_get_update()
            if not result.success:
                raise ProvisionException('apt-get update: {0.std_err}'.format(result))
            result = apt_get_install(context.package.arg)
            if not result.success:
                raise ProvisionException('Installation of {0} failed: {1.std_err}'.format(context.package.arg,
                                                                                          result))
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
        log.debug('Mounts configured')
        if os.path.isfile('/etc/resolv.conf'):
            log.debug('Copying in a temporary resolv.conf')
            try:
                shutil.copy('/etc/resolv.conf', os.path.join(self.mountpoint, 'etc/resolv.conf'))
            except Exception, e:
                log.debug('Exception copying resolv.conf: {0}'.format(e))
                log.debug(os.listdir(self.mountpoint))
                log.debug(os.listdir(os.path.join(self.mountpoint, 'etc')))
        else:
            log.info('unable to find a suitable resolv.conf to copy into the chroot env')

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

        resolv = os.path.join(self.mountpoint, 'etc/resolv.conf')
        if os.path.exists(resolv):
            log.debug('removing temporary resolv.conf at {0}'.format(resolv))
            os.remove(resolv)

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