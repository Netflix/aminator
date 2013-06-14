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
aminator.plugins.provisioner.apt_chef
================================
basic apt chef provisioner.  assumes the base ami has chef installed
"""
import logging
import os
import shutil
from collections import namedtuple

from aminator.plugins.provisioner.linux import BaseLinuxProvisionerPlugin
from aminator.plugins.provisioner.apt import AptProvisionerPlugin
from aminator.util.linux import command
from aminator.util.linux import short_circuit_files, rewire_files, Chroot
from aminator.config import conf_action

__all__ = ('AptChefProvisionerPlugin',)
log = logging.getLogger(__name__)

CommandResult = namedtuple('CommandResult', 'success result')
CommandOutput = namedtuple('CommandOutput', 'std_out std_err')

class AptChefProvisionerPlugin(BaseLinuxProvisionerPlugin):
    """
    AptChefProvisionerPlugin takes the majority of its behavior from BaseLinuxProvisionerPlugin
    See BaseLinuxProvisionerPlugin for details
    """
    _name = 'apt_chef'

    def add_plugin_args(self):
        context = self._config.context
        chef_config = self._parser.add_argument_group(title='Chef Solo Options', description='Options for the chef solo provisioner')

        chef_config.add_argument('-j', '--json-attributes', dest='json', 
				 help='Chef JSON file (the same as running chef-solo -j)',
				 action=conf_action(config=context.chef))
        chef_config.add_argument('-o', '--override-runlist', dest='override', 
                                 help='Run this comma-separated list of items (the same as running chef-solo -o)',
				 action=conf_action(config=context.chef))

    def _refresh_package_metadata(self):
        """
	Pass thru to the AptProvisioner method
        """
        apt_provisioner = AptProvisionerPlugin()
        return apt_provisioner._refresh_package_metadata()


    def _provision_package(self):
        context = self._config.context
        config = self._config.plugins[self.full_name]

        log.debug('Running chef-solo for run list items: %s' % config.get('runlist'))
        return chef_solo(config.get('runlist'))


    def _store_package_metadata(self):
        """
	Pass thru to the AptProvisioner method, but using our configs
        """
        
        # since there isn't a package to get this info from, we'll need to be told
        # this stuff.  I'm thinking we could add it to the json file which is 
        # name = cookbook/role name
        # version = cookbook version
        # hopefully auto-generated from Jenkins

	context = self._config.context
        context.package.attributes = { 'name': context.chef.json, 'version': 0.1, 'release': 0 }


    def _deactivate_provisioning_service_block(self):
        """
        Prevent packages installing in the chroot from starting
        For debian based distros, we add /usr/sbin/policy-rc.d
        """

        config = self._config.plugins[self.full_name]
        path = self._mountpoint + config.get('policy_file_path', '')
        filename = path + "/" + config.get('policy_file')

        if not os.path.isdir(path):
            log.debug("creating %s", path)
            os.makedirs(path)
            log.debug("created %s", path)

        with open(filename, 'w') as f:
            log.debug("writing %s", filename)
            f.write(config.get('policy_file_content'))
            log.debug("wrote %s", filename)

        os.chmod(filename, config.get('policy_file_mode', ''))

        return True

    def _activate_provisioning_service_block(self):
        """
        Remove policy-rc.d file so that things start when the AMI launches
        """
        config = self._config.plugins[self.full_name]

        policy_file = self._mountpoint + "/" + config.get('policy_file_path', '') + "/" + \
            config.get('policy_file', '')

        if os.path.isfile(policy_file):
            log.debug("removing %s", policy_file)
            os.remove(policy_file)
        else:
            log.debug("The %s was missing, this is unexpected as the "
                      "AptChefProvisionerPlugin should manage this file", policy_file)

        return True

    def provision(self):
        context = self._config.context

        """
	  for simple chef run, we need a json file (or -o?) tell what recipes to execute
	  - JSON file
          - solo.rb
   
          next steps:
          - load JSON from URL
          - support -o
          - copy in cookbooks?
	"""
	
       # TODO stage JSON
        log.debug('Entering chroot at {0}'.format(self._mountpoint))

	context = self._config.context
        config = self._config
	context.package.dir = config.plugins[self.full_name].get('chef_dir', '/var/chef')

	# hold onto these as _stage_pkg mutates context.package.arg
	context.chef.setdefault('dir', context.package.dir)
        if context.package.arg.startswith('http://'):
	    context.chef.setdefault('json', context.package.arg.split('/')[-1])
	else:
	    context.chef.setdefault('json', context.package.arg)

        log.debug('Pre chroot command block')
        self._pre_chroot_block()

	log.debug('before _stage_pkg context.package.dir = {0}'.format(context.package.dir))
	log.debug('before _stage_pkg context.package.arg = {0}'.format(context.package.arg))

        if not self._stage_pkg():
            log.critical('failed to stage {0}'.format(context.package.arg))
            return False

	log.debug('after _stage_pkg context.package.dir = {0}'.format(context.package.dir))
	log.debug('after _stage_pkg context.package.arg = {0}'.format(context.package.arg))

        with Chroot(self._mountpoint):
            log.debug('Inside chroot')

            log.debug('Preparing to run chef-solo')
            result = chef_solo(context.chef.dir, context.chef.json)
            if not result.success:
                log.critical('chef-solo run failed: {0.std_err}'.format(result.result))
                return False

            self._store_package_metadata()

        log.debug('Exited chroot')

        log.debug('Post chroot command block')
        self._post_chroot_block()

        log.info('Provisioning succeeded!')

        return True

@command()
def chef_solo(chef_dir, chef_json):
    # If run list is not specific, dont override it on the command line
    # if runlist:
    #     return 'chef-solo -j /tmp/node.json -c /tmp/solo.rb -o {0}'.format(runlist)
    # else:
    log.debug('Preparing to run chef-solo {0}'.format(chef_json))
    return 'chef-solo -j {0}/{1} -c {0}/solo.rb'.format(chef_dir, chef_json)
