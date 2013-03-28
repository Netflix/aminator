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

from aminator.plugins.provisioner.linux import BaseLinuxProvisionerPlugin, WELL_KNOWN_PACKAGE_NAME
from aminator.util.linux import sanitize_metadata, command

__all__ = ('AptProvisionerPlugin',)
log = logging.getLogger(__name__)


class AptProvisionerPlugin(BaseLinuxProvisionerPlugin):
    """
    AptProvisionerPlugin takes the majority of its behavior from BaseLinuxProvisionerPlugin
    See BaseLinuxProvisionerPlugin for details
    """
    _name = 'apt'

    def _refresh_package_metadata(self):
        return apt_get_update()

    def _provision_package(self):
        context = self._config.context
        os.environ['DEBIAN_FRONTEND'] = 'noninteractive'
        if context.package.local_package:
            return dpkg_install(WELL_KNOWN_PACKAGE_NAME)
        else:
            return apt_get_install(context.package.arg)

    def _store_package_metadata(self):
        context = self._config.context
        if context.package.local_package:
            result = deb_local_package_query(WELL_KNOWN_PACKAGE_NAME)
        else:
            result = deb_query(context.package.arg)
        metadata = self.__deb_extract_metadata(result)
        context.package.name = metadata.get('name', context.package.arg)
        context.package.version = metadata.get('version', '_')
        context.package.release = metadata.get('release', '_')

    def __deb_extract_metadata(self, result):
        metadata = {}
        if result.success:
            for line in result.result.std_out.split('\n'):
                if line.strip().startswith('Package:'):
                    log.debug('Package in {0}'.format(line))
                    metadata['name'] = sanitize_metadata(line.split(':')[1].strip())
                elif line.strip().startswith('Version:'):
                    log.debug('Version in {0}'.format(line))
                    metadata['version'] = sanitize_metadata(line.split(':')[1].strip())
                else:
                    log.debug('No tags'.format(line))
                    continue
        return metadata

#
# Below are Debian specific package management commands
#

@command()
def apt_get_update():
    return 'apt-get update'


@command()
def apt_get_install(package):
    return 'apt-get -y install {0}'.format(package)

@command()
def dpkg_install(package):
    return 'dpkg -i {0}'.format(package)

@command()
def deb_query(package):
    return 'dpkg -p {0}'.format(package)

@command()
def deb_local_package_query(package):
    return 'dpkg -I {0}'.format(package)

