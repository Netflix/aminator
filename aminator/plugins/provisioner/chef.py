# -*- coding: utf-8 -*-

#
#
#  Copyright 2013 Riot Games
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
from aminator.util.linux import short_circuit_files, rewire_files
from aminator.config import conf_action

__all__ = ('ChefProvisionerPlugin',)
log = logging.getLogger(__name__)
CommandResult = namedtuple('CommandResult', 'success result')

class ChefProvisionerPlugin(BaseLinuxProvisionerPlugin):
    """
    ChefProvisionerPlugin takes the majority of its behavior from BaseLinuxProvisionerPlugin
    See BaseLinuxProvisionerPlugin for details
    """
    _name = 'chef'

    def add_plugin_args(self):
        context = self._config.context
        chef_config = self._parser.add_argument_group(title='Chef Solo Options', description='Required options for running chef-solo provisioner')

        chef_config.add_argument('-a', '--alias', dest='alias', help='Alias for the runlist items. This will be used as the name for the ami',
                                 action=conf_action(self._config.plugins[self.full_name]))
        chef_config.add_argument('--payload-url', dest='payload_url', help='Location to fetch the payload from',
                                 action=conf_action(self._config.plugins[self.full_name]))
        chef_config.add_argument('--payload-version', dest='payload_version', help='Payload version',
                                 action=conf_action(self._config.plugins[self.full_name]))
        chef_config.add_argument('--payload-release', dest='payload_release', help='Payload release',
                                 action=conf_action(self._config.plugins[self.full_name]))
        chef_config.add_argument('--chef-version', dest='chef_version', help='Version of chef to install', default="10.18.0",
                                 action=conf_action(self._config.plugins[self.full_name]))
        

    def _refresh_package_metadata(self):
        """
        Fetch the latest version of cookbooks and JSON node info
        """
        config          = self._config.plugins[self.full_name]
        payload_url     = config.get('payload-url')
        chef_version    = config.get('chef_version')

        if os.path.exists("/opt/chef/bin/chef-solo"):
            log.debug('Omnibus chef is already installed, skipping install')
        else:
            log.debug('Installing omnibus chef-solo')
            result = install_omnibus_chef(chef_version)
            if not result.success:
                log.critical('Failed to install chef')
                return result

        log.debug('Downloading payload from %s' % payload_url)
        payload_result = fetch_chef_payload(payload_url)

        return payload_result

    def _provision_package(self):
        config          = self._config.plugins[self.full_name]
        alias           = config.get('alias')
        payload_url     = config.get('payload-url')
        payload_version = config.get('payload-version')
        payload_release = config.get('payload-release')
        chef_version    = config.get('chef-version')

        if not alias:
            log.critical('Missing argument for chef provisioner: --alias')
            return None

        if not payload_url:
            log.critical('Missing argument for chef provisioner: --payload-url')
            return None

        if not payload_version:
            log.critical('Missing argument for chef provisioner: --payload-version')
            return None

        if not payload_release:
            log.critical('Missing argument for chef provisioner: --payload-release')
            return None

        if not chef_version:
            log.critical('Missing argument for chef provisioner: --chef-version')
            return None

        pass
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
        """
        Prevent packages installing the chroot from starting
        For RHEL-like systems, we can use short_circuit which replaces the service call with /bin/true
        """
        config = self._config.plugins[self.full_name]
        files = config.get('short_circuit_files', [])
        if files:
            if not short_circuit_files(self._mountpoint, files):
                log.critical('Unable to short circuit {0} to {1}')
                return False
            else:
                log.debug('Files short-circuited successfully')
                return True
        else:
            log.debug('No short circuit files configured')
            return True

    def _activate_provisioning_service_block(self):
        """
        Enable service startup so that things work when the AMI starts
        For RHEL-like systems, we undo the short_circuit
        """
        config = self._config.plugins[self.full_name]
        files = config.get('short_circuit_files', [])
        if files:
            if not rewire_files(self._mountpoint, files):
                log.critical('Unable to rewire {0} to {1}')
                return False
            else:
                log.debug('Files rewired successfully')
                return True
        else:
            log.debug('No short circuit files configured, no rewiring done')
        return True


@command()
def curl_download(src, dst):
    return 'curl {0} -o {1}'.format(src, dst)


@command()
def install_omnibus_chef(chef_version = None):
    curl_download('https://www.opscode.com/chef/install.sh', '/tmp/install-chef.sh')

    if chef_version:
        return 'bash /tmp/install-chef.sh -v {0}'.format(chef_version)
    else:
        return 'bash /tmp/install-chef.sh'


@command()
def chef_solo(runlist):
    return 'chef-solo -j /tmp/node.json -c /tmp/solo.rb -o {0}'.format(runlist)


@command()
def fetch_chef_payload(payload_url):
    curl_download(payload_url, '/tmp/foo.tar.gz')

    return 'tar -C / -xf /tmp/foo.tar.gz'.format(payload_url)
