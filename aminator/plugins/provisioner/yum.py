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

from aminator.plugins.provisioner.base import BaseProvisionerPlugin
from aminator.util.linux import monitor_command, result_to_dict
from aminator.util.metrics import cmdsucceeds, cmdfails, lapse

__all__ = ('YumProvisionerPlugin',)
log = logging.getLogger(__name__)


class YumProvisionerPlugin(BaseProvisionerPlugin):
    """
    YumProvisionerPlugin takes the majority of its behavior from BaseProvisionerPlugin
    See BaseProvisionerPlugin for details
    """
    _name = 'yum'

    def _refresh_repo_metadata(self):
        config = self._config.plugins[self.full_name]
        return yum_clean_metadata(config.get('clean_repos', []))

    @cmdsucceeds("aminator.provisioner.yum.provision_package.count")
    @cmdfails("aminator.provisioner.yum.provision_package.error")
    @lapse("aminator.provisioner.yum.provision_package.duration")
    def _provision_package(self):
        result = self._refresh_repo_metadata()
        if not result.success:
            log.critical('Repo metadata refresh failed: {0.std_err}'.format(result.result))
            return result
        context = self._config.context
        if context.package.get('local_install', False):
            return yum_localinstall(context.package.arg)
        else:
            return yum_install(context.package.arg)

    def _store_package_metadata(self):
        context = self._config.context
        config = self._config.plugins[self.full_name]
        metadata = rpm_package_metadata(context.package.arg, config.get('pkg_query_format', ''), context.package.get('local_install', False))
        for x in config.pkg_attributes:
            metadata.setdefault(x, None)
        context.package.attributes = metadata


def yum_install(package):
    return monitor_command(['yum', '--nogpgcheck', '-y', 'install', package])


def yum_localinstall(path):
    if not os.path.isfile(path):
        log.critical('Package {0} not found'.format(path))
        return None
    return monitor_command(['yum', '--nogpgcheck', '-y', 'localinstall', path])


def yum_clean_metadata(repos=None):
    clean = ['yum', 'clean', 'metadata']
    if repos:
        clean.extend(['--disablerepo', '*', '--enablerepo', ','.join(repos)])
    return monitor_command(clean)


def rpm_query(package, queryformat, local=False):
    cmd = 'rpm -q --qf'.split()
    cmd.append(queryformat)
    if local:
        cmd.append('-p')
    cmd.append(package)
    return monitor_command(cmd)


def rpm_package_metadata(package, queryformat, local=False):
    return result_to_dict(rpm_query(package, queryformat, local))
