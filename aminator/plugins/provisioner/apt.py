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

    def _deactivate_provisioning_service_block(self):
        """
        Prevent packages installing in the chroot from starting
        For debian based distros, we add /usr/sbin/policy-rc.d
        """

        config = self._config.plugins[self.full_name]
        path = self._mountpoint + config.get('policy_file_path', '')
        filename = path + "/" + config.get('policy_file')

        if not os.path.isdir(path):
            log.debug("creating %s", path)
            os.makedirs(path)
            log.debug("created %s", path)

        with open(filename, 'w') as f:
            log.debug("writing %s", filename)
            f.write(self.POLICY_FILE_CONTENT.lstrip())
            log.debug("wrote %s", filename)

        os.chmod(filename, config.get('policy_file_mode', ''))

        return True

    def _activate_provisioning_service_block(self):
        """
        Remove policy-rc.d file so that things start when the AMI launches
        """
        config = self._config.plugins[self.full_name]

        policy_file = self._mountpoint + "/" + config.get('policy_file_path', '') + "/" + \
                      config.get('policy_file', '')

        if os.path.isfile(policy_file):
            log.debug("removing %s", policy_file)
            os.remove(policy_file)
        else:
            log.debug("The %s was missing, this is unexpected as the "
                      "AptProvisionerPlugin should manage this file", policy_file)

        return True
