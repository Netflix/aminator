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

    def _refresh_package_metadata(self):
        return apt_get_update()

    def _provision_package(self):
        context = self._config.context
        os.environ['DEBIAN_FRONTEND'] = 'noninteractive'
        return apt_get_install(context.package.arg)

    def _store_package_metadata(self):
        context = self._config.context
        config = self._config.plugins[self.full_name]
        metadata = deb_package_metadata(context.package.arg, config.get('pkg_query_format', ''))
        for x in config.pkg_attributes:
            if x == 'version':
                if x in metadata and ':' in metadata[x]:
                    # strip epoch element from version
                    vers = metadata[x]
                    metadata[x] = vers[vers.index(':')+1:]
                if '-' in metadata[x]:
                    # debs include release in version so split
                    # version into version-release to compat w/rpm
                    vers, rel = metadata[x].split('-', 1)
                    metadata[x] = vers
                    metadata['release'] = rel
                else:
                    metadata['release'] = 0
            # this is probably not necessary given above
            metadata.setdefault(x, None)
        context.package.attributes = metadata
