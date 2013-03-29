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
import os, errno

from aminator.plugins.provisioner.linux import BaseLinuxProvisionerPlugin
from aminator.util.linux import apt_get_install, apt_get_update, deb_package_metadata

__all__ = ('AptProvisionerPlugin',)
log = logging.getLogger(__name__)


class AptProvisionerPlugin(BaseLinuxProvisionerPlugin):
    """
    AptProvisionerPlugin takes the majority of its behavior from BaseLinuxProvisionerPlugin
    See BaseLinuxProvisionerPlugin for details
    """
    _name = 'apt'

    POLICY_FILE = 'policy-rc.d'
    POLICY_FILE_MODE = 0755
    POLICY_FILE_PATH = '/usr/sbin'
    POLICY_FILE_CONTENT = """
#!/bin/sh
exit 101"""

    def _refresh_package_metadata(self):
        return apt_get_update()

    def _provision_package(self):
        context = self._config.context
        os.environ['DEBIAN_FRONTEND'] = 'noninteractive'
        return apt_get_install(context.package.arg)

    def _store_package_metadata(self):
        context = self._config.context
        metadata = deb_package_metadata(context.package.arg)
        context.package.name = metadata.get('name', context.package.arg)
        context.package.version = metadata.get('version', '_')
        context.package.release = metadata.get('release', '_')

    def _disable_service_startup(self):
        """
        Prevent packages installing in the chroot from starting
        For debian based distros, we add /usr/sbin/policy-rc.d
        """

        path = self._mountpoint + self.POLICY_FILE_PATH
        filename = path + "/" + self.POLICY_FILE

        try:
            log.debug("creating %s", path)
            os.makedirs(path)
            log.debug("created %s", path)
        except OSError as exc:
            if exc.errno == errno.EEXIST and os.path.isdir(path):
                pass
            else:
                raise

        with open(filename, 'w') as f:
            log.debug("writing %s", filename)
            f.write(self.POLICY_FILE_CONTENT.lstrip())
            os.chmod(filename, self.POLICY_FILE_MODE)
            log.debug("wrote %s", filename)

        return True

    def _enable_service_startup(self):
        """
        Enable service startup so that things work when the AMI starts
        """
        full_path = self._mountpoint + "/" + AptProvisionerPlugin.POLICY_FILE_PATH + "/" + \
                         AptProvisionerPlugin.POLICY_FILE
        try:
            os.remove(full_path)
        except OSError:
            pass

        return True
