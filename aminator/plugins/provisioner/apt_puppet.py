# -*- coding: utf-8 -*-

#
#
#  Copyright 2013 Netflix
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
aminator.plugins.provisioner.apt_puppet
================================
"""
import pprint
import logging
from collections import namedtuple
import json

from aminator.plugins.provisioner.apt import AptProvisionerPlugin, dpkg_install
from aminator.util import download_file
from aminator.util.linux import command
from aminator.util.linux import Chroot
from aminator.config import conf_action

__all__ = ('AptPuppetProvisionerPlugin',)
log = logging.getLogger(__name__)

CommandResult = namedtuple('CommandResult', 'success result')
CommandOutput = namedtuple('CommandOutput', 'std_out std_err')


class AptPuppetProvisionerPlugin(AptProvisionerPlugin):
    """
    AptPuppetProvisionerPlugin takes the majority of its behavior from AptProvisionerPlugin
    See AptProvisionerPlugin for details
    """
    _name = 'apt_puppet'

    def add_plugin_args(self):
        context = self._config.context
        puppet_config = self._parser.add_argument_group(title='Puppet Options',
                                                      description='Options for the puppet provisioner')
        puppet_config.add_argument('-H', '--puppet-agent-hostname', dest='puppet_agent_hostname',
                                    action=conf_action(config=context.puppet),
                                    help='A temporary hostname for the chrooted environment that indicates to puppet what catalog to apply')


    def _store_package_metadata(self):
        """
        save info for the AMI we're building in the context so that it can be incorporated into tags and the description
        during finalization. these values come from the chef JSON node file since we can't query the package for these
        attributes
        """
        context = self._config.context

	context.package.attributes = {"foo": "bar"}

    def provision(self):
        """
        overrides the base provision
          * store the chef JSON file information in the context
          * install chef from a URL if specified
          * call chef-solo
        """

        log.debug('Entering chroot at {0}'.format(self._mountpoint))

        context = self._config.context
        config = self._config
        context.package.dir = config.plugins[self.full_name].get('puppet_dir', '/var/chef')

        # hold onto the JSON info as _stage_pkg mutates context.package.arg
        context.chef.setdefault('dir', context.package.dir)
        if context.package.arg.startswith('http://'):
            context.chef.setdefault('json', context.package.arg.split('/')[-1])
        else:
            context.chef.setdefault('json', context.package.arg)

        # copy the JSON file to chef_dir in the chroot.  mkdirs in case we've never installed chef
        full_chef_dir_path = self._mountpoint + context.chef.dir
        log.debug('prepping chef_dir {0}'.format(full_chef_dir_path))
        mkdirs(full_chef_dir_path)

        if not self._stage_pkg():
            log.critical('failed to stage {0}'.format(context.package.arg))
            return False

        with Chroot(self._mountpoint):
            log.debug('Inside chroot')

            dpkg_install("puppet")

            log.debug('Preparing to run puppet')

            self._store_package_metadata()

        log.debug('Exited chroot')

        log.info('Provisioning succeeded!')

        return True


@command()
def mkdirs(dirs):
    return 'mkdir -p {0}'.format(dirs)


@command()
def puppet():
    pass
