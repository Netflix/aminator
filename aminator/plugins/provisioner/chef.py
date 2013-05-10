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
aminator.plugins.provisioner.chef
================================
basic chef provisioner
"""
import logging
import os

from aminator.plugins.provisioner.linux import BaseLinuxProvisionerPlugin
from aminator.util.linux import command

__all__ = ('chefProvisionerPlugin',)
log = logging.getLogger(__name__)


class chefProvisionerPlugin(BaseLinuxProvisionerPlugin):
    """
    chefProvisionerPlugin takes the majority of its behavior from BaseLinuxProvisionerPlugin
    See BaseLinuxProvisionerPlugin for details
    """
    _name = 'chef'

    def _refresh_package_metadata(self):
       """
       Fetch the latest version of cookbooks
       """
       return True

    def _provision_package(self):
        print "chef-solo --runlist %s" % context.package.arg
        return True
        return chef_solo(context.package.arg)

    def _store_package_metadata(self):
        context = self._config.context
        context.package.attributes = { 'name': 'chef', 'version': '0.0.1', 'release': '0' }

    def _deactivate_provisioning_service_block(self):
        return True

    def _activate_provisioning_service_block(self):
        return True


@command()
def chef_solo(runlist):
    return 'chef-solo -r {0}'.format(runlist)
