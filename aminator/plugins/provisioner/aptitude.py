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
import re

from aminator.plugins.provisioner.apt import AptProvisionerPlugin
from aminator.util.linux import monitor_command

__all__ = ('AptitudeProvisionerPlugin',)
log = logging.getLogger(__name__)


class AptitudeProvisionerPlugin(AptProvisionerPlugin):
    """
    AptitudeProvisionerPlugin takes the majority of its behavior from AptProvisionerPlugin
    See AptProvisionerPlugin for details
    """
    _name = 'aptitude'

    # overload this method to call aptitude instead.
    @classmethod
    def apt_get_localinstall(cls, package):
        """install deb file with dpkg then resolve dependencies
        """
        dpkg_ret = cls.dpkg_install(package)
        pkgname, pkgver, _ = basename(package).split('_')
        if not dpkg_ret.success:
            log.debug('failure:{0.command} :{0.std_err}'.format(dpkg_ret.result))
            aptitude_ret = cls.aptitude("install", "{}={}".format(pkgname, pkgver))
            if not aptitude_ret.success:
                log.debug('failure:{0.command} :{0.std_err}'.format(aptitude_ret.result))
            query_ret = super(AptitudeProvisionerPlugin,cls).deb_query(pkgname, "${Status}", local=False)
            if not query_ret.success:
                log.debug('failure:{0.command} :{0.std_err}'.format(query_ret.result))
            if "install ok installed" not in query_ret.result.std_out:
                raise RuntimeError("package {} failed to be installed.  dpkg status: {}".format(pkgname, query_ret.result.std_out))
            return query_ret
        return dpkg_ret

    @staticmethod
    def aptitude(operation, package):
        return monitor_command(["aptitude", "--no-gui", "-y", operation, package])

    # overload this method to call aptitude instead.  But aptitude will not exit with
    # an error code if it failed to install, so we double check that the package installed
    # with the dpkg-query command
    @classmethod
    def apt_get_install(cls,package):
        aptitude_ret = cls.aptitude("install", package)
        if not aptitude_ret.success:
            log.debug('failure:{0.command} :{0.std_err}'.format(aptitude_ret.result))
        query_ret = cls.deb_query(package, '${Package}-${Version}')
        if not query_ret.success:
            log.debug('failure:{0.command} :{0.std_err}'.format(query_ret.result))
        return query_ret
