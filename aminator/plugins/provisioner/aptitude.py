# -*- coding: utf-8 -*-

#
#
#  Copyright 2014 Netflix, Inc.
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
aminator.plugins.provisioner.aptitude
================================
basic aptitude provisioner

Note:

Aptitude resolvers by default are a bit crazy.  The "best" solution it finds is often to remove what
you asked it to install.  To make Aptitude resolvers sane create a config file like:
$ cat /etc/apt/apt.conf.d/00aptitude-sane-resolve.conf
Aptitude {
    ProblemResolver {
        SolutionCost "priority, removals, canceled-actions";
    };
};

For futher reading checkout:
http://www.proulx.com/~bob/debian/hints/jessie-new.html
https://lists.debian.org/debian-devel/2014/10/msg00424.html
"""
import logging

from os.path import basename

from aminator.exceptions import ProvisionException
from aminator.plugins.provisioner.apt import AptProvisionerPlugin
from aminator.util.linux import monitor_command

__all__ = ('AptitudeProvisionerPlugin',)
log = logging.getLogger(__name__)


class AptitudeInstallException(ProvisionException):
    pass


class AptitudeProvisionerPlugin(AptProvisionerPlugin):
    """
    AptitudeProvisionerPlugin takes the majority of its behavior from AptProvisionerPlugin
    See AptProvisionerPlugin for details
    """
    _name = 'aptitude'

    # overload this method to call aptitude instead.
    def _fix_localinstall_deps(self, package):
        # use aptitude and its solver to resolve dependencies after a dpkg -i
        pkgname, _, _ = basename(package).split('_')

        # figure out the version via dpkg rather than parsing it out of the file name
        # in case there is an epoch in the version
        version_query_ret = self.deb_query(package, "${Version}", local=True)
        if not version_query_ret.success:
            log.critical("Unable to query version for package {0}".format(package))
            return version_query_ret
        pkgver = version_query_ret.result.std_out

        aptitude_ret = self.aptitude("install", "{0}={1}".format(pkgname, pkgver))
        if not aptitude_ret.success:
            log.critical("Error encountered resolving dependencies for package {0}: "
                         "{1.std_err}".format(package, aptitude_ret.result))
            return aptitude_ret

        install_query_ret = self.deb_query(pkgname, "${Status} ${Version}", local=False)
        if not install_query_ret.success:
            log.critical("Error querying installation status for package {0}: "
                         "{1.std_err}".format(package, install_query_ret.result))
            return install_query_ret

        if "install ok installed" not in install_query_ret.result.std_out:
            errmsg = "package {0} failed to be installed. dpkg status: {1.std_out}"
            errmsg = errmsg.format(package, install_query_ret.result)
            raise AptitudeInstallException(errmsg)

        installed_version = install_query_ret.result.std_out.split()[-1].strip()
        if installed_version != pkgver:
            errmsg = "package {0} failed to be installed. requested {1}, installed {2}"
            errmsg = errmsg.format(pkgname, pkgver, installed_version)
            raise AptitudeInstallException(errmsg)

        return install_query_ret

    @staticmethod
    def aptitude(operation, package):
        aptitude_result = monitor_command(["aptitude", "--no-gui", "-y", operation, package])
        if not aptitude_result.success:
            log.debug('failure:{0.command} :{0.std_err}'.format(aptitude_result.result))
        return aptitude_result

    # overload this method to call aptitude instead.  But aptitude will not exit with
    # an error code if it failed to install, so we double check that the package installed
    # with the dpkg-query command
    def _install(self, package):
        self.aptitude("install", package)
        query_ret = self.deb_query(package, '${Package}-${Version}')
        if not query_ret.success:
            errmsg = "Error installing package {0}: {1.std_err}"
            errmsg = errmsg.format(package, query_ret.result)
            log.critical(errmsg)
        return query_ret
