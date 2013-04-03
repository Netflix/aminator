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

from aminator.plugins.provisioner.linux import BaseLinuxProvisionerPlugin
from aminator.util.linux import command, keyval_parse

__all__ = ('YumProvisionerPlugin',)
log = logging.getLogger(__name__)


class YumProvisionerPlugin(BaseLinuxProvisionerPlugin):
    """
    YumProvisionerPlugin takes the majority of its behavior from BaseLinuxProvisionerPlugin
    See BaseLinuxProvisionerPlugin for details
    """
    _name = 'yum'

    def _refresh_package_metadata(self):
        return yum_clean_metadata()

    def _provision_package(self):
        context = self._config.context
        return yum_install(context.package.arg)

    def _store_package_metadata(self):
        context = self._config.context
        config = self._config.plugins[self.full_name]
        metadata = rpm_package_metadata(context.package.arg, config.get('pkg_query_format', ''))
        for x in config.pkg_attributes:
            metadata.setdefault(x, None)
        context.package.attributes = metadata


@keyval_parse()
def rpm_package_metadata(package, queryformat):
    return rpm_query(package, queryformat)


@command()
def yum_install(package):
    return 'yum --nogpgcheck -y install {0}'.format(package)


@command()
def yum_localinstall(path):
    if not os.path.isfile(path):
        log.critical('Package {0} not found'.format(path))
        return None
    return 'yum --nogpgcheck -y localinstall {0}'.format(path)


@command()
def yum_clean_metadata():
    return 'yum clean metadata'

@command()
def rpm_query(package, queryformat):
    cmd = 'rpm -q --qf'.split()
    cmd.append(queryformat)
    cmd.append(package)
    return cmd