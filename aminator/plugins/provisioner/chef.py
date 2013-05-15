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
from collections import namedtuple

from aminator.plugins.provisioner.linux import BaseLinuxProvisionerPlugin
from aminator.util.linux import command

__all__ = ('ChefProvisionerPlugin',)
log = logging.getLogger(__name__)
CommandResult = namedtuple('CommandResult', 'success result')

class ChefProvisionerPlugin(BaseLinuxProvisionerPlugin):
    """
    ChefProvisionerPlugin takes the majority of its behavior from BaseLinuxProvisionerPlugin
    See BaseLinuxProvisionerPlugin for details
    """
    _name = 'chef'

    def _refresh_package_metadata(self):
        """
        Fetch the latest version of cookbooks and JSON node info
        """
        config = self._config.plugins[self.full_name]
        payload_url = config.get('cookbook_url')

        log.debug('Downloading payload from %s' % json_url)
        payload_result = fetch_chef_payload(payload_url)

        return payload_result

    def _provision_package(self):
        context = self._config.context
        log.debug('Running chef-solo for runlist items: %s' % context.package.arg)
        chef_result = chef_solo(context.package.arg)

        return chef_result

    def _store_package_metadata(self):
        context = self._config.context
        config = self._config.plugins[self.full_name]

        name    = config.get('name')
        version = config.get('version')
        release = config.get('release')

        context.package.attributes = { 'name': name, 'version': version, 'release': release }

    def _deactivate_provisioning_service_block(self):
        return CommandResult(True, object())

    def _activate_provisioning_service_block(self):
        return CommandResult(True, object())


@command()
def chef_solo(runlist):
    return 'chef-solo -j /tmp/node.json -c /tmp/solo.rb -o {0}'.format(runlist)


@command()
def fetch_chef_payload(payload_url):
    return 'curl -s -0 {0} | tar -C / -xzf -'.format(cookbook_url)
