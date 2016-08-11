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

from aminator.exceptions import ProvisionException
from aminator.plugins.provisioner.base import BaseProvisionerPlugin
from aminator.util import retry
from aminator.util.linux import monitor_command, result_to_dict
from aminator.util.metrics import cmdsucceeds, cmdfails, timer, lapse

__all__ = ('AptProvisionerPlugin',)
log = logging.getLogger(__name__)


class AptProvisionerUpdateException(ProvisionException):
    pass


class AptProvisionerPlugin(BaseProvisionerPlugin):
    """
    AptProvisionerPlugin takes the majority of its behavior from BaseProvisionerPlugin
    See BaseProvisionerPlugin for details
    """
    _name = 'apt'

    @cmdsucceeds("aminator.provisioner.apt.provision_package.count")
    @cmdfails("aminator.provisioner.apt.provision_package.error")
    @lapse("aminator.provisioner.apt.provision_package.duration")
    def _provision_package(self):
        context = self._config.context
        os.environ['DEBIAN_FRONTEND'] = 'noninteractive'
        return self.install(context.package.arg,
                            local_install=context.package.get('local_install', False))

    def _store_package_metadata(self):
        context = self._config.context
        config = self._config.plugins[self.full_name]
        metadata = self.deb_package_metadata(context.package.arg, config.get('pkg_query_format', ''), context.package.get('local_install', False))
        for x in config.pkg_attributes:
            if x == 'version' and x in metadata:
                if ':' in metadata[x]:
                    # strip epoch element from version
                    vers = metadata[x]
                    metadata[x] = vers[vers.index(':') + 1:]
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

    @staticmethod
    def dpkg_install(package):
        dpkg_result = monitor_command(['dpkg', '-i', package])
        if not dpkg_result.success:
            log.debug('failure:{0.command} :{0.std_err}'.format(dpkg_result.result))
        return dpkg_result

    def _fix_localinstall_deps(self, package):
        # use apt-get to resolve dependencies after a dpkg -i
        fix_deps_result = self.apt_get_install('--fix-missing')
        if not fix_deps_result.success:
            log.debug('failure:{0.command} :{0.std_err}'.format(fix_deps_result.result))
        return fix_deps_result

    def _localinstall(self, package):
        """install deb file with dpkg then resolve dependencies
        """
        dpkg_ret = self.dpkg_install(package)
        if not dpkg_ret.success:
            # expected when package has dependencies that are not installed
            update_metadata_result = self.apt_get_update()
            if not update_metadata_result.success:
                errmsg = 'Repo metadata refresh failed: {0.std_err}'
                errmsg = errmsg.format(update_metadata_result.result)
                return update_metadata_result
            log.info("Installing dependencies for package {0}".format(package))
            fix_deps_result = self._fix_localinstall_deps(package)
            if not fix_deps_result.success:
                log.critical("Error encountered installing dependencies: "
                             "{0.std_err}".format(fix_deps_result.result))
            return fix_deps_result
        return dpkg_ret

    @staticmethod
    def deb_query(package, queryformat, local=False):
        if local:
            cmd = 'dpkg-deb -W'.split()
            cmd.append('--showformat={0}'.format(queryformat))
        else:
            cmd = 'dpkg-query -W'.split()
            cmd.append('-f={0}'.format(queryformat))
        cmd.append(package)
        deb_query_result = monitor_command(cmd)
        if not deb_query_result.success:
            log.debug('failure:{0.command} :{0.std_err}'.format(deb_query_result.result))
        return deb_query_result

    @cmdsucceeds("aminator.provisioner.apt.apt_get_update.count")
    @cmdfails("aminator.provisioner.apt.apt_get_update.error")
    @timer("aminator.provisioner.apt.apt_get_update.duration")
    @retry(ExceptionToCheck=AptProvisionerUpdateException, tries=5, delay=1, backoff=0.5, logger=log)
    def apt_get_update(self):
        self.apt_get_clean()
        dpkg_update = monitor_command(['apt-get', 'update'])
        if not dpkg_update.success:
            log.debug('failure: {0.command} :{0.std_err}'.format(dpkg_update.result))
            # trigger retry. expiring retries should fail the bake as this
            # exception will propagate out to the provisioning context handler
            raise AptProvisionerUpdateException('apt-get update failed')
        return dpkg_update

    @staticmethod
    def apt_get_clean():
        return monitor_command(['apt-get', 'clean'])

    @staticmethod
    def apt_get_install(*options):
        cmd = ['apt-get', '-y', 'install']
        cmd.extend(options)
        install_result = monitor_command(cmd)
        if not install_result.success:
            log.debug('failure:{0.command} :{0.std_err}'.format(install_result.result))
        return install_result

    def _install(self, package):
        return self.apt_get_install(package)

    def install(self, package, local_install=False):
        if local_install:
            install_result = self._localinstall(package)
        else:
            update_metadata_result = self.apt_get_update()
            if not update_metadata_result.success:
                errmsg = 'Repo metadata refresh failed: {0.std_err}'
                errmsg = errmsg.format(update_metadata_result.result)
                return update_metadata_result
            install_result = self._install(package)
        if not install_result.success:
            errmsg = 'Error installing package {0}: {1.std_err}'
            errmsg = errmsg.format(package, install_result.result)
            log.critical(errmsg)
        return install_result

    @classmethod
    def deb_package_metadata(cls, package, queryformat, local=False):
        return result_to_dict(cls.deb_query(package, queryformat, local))
