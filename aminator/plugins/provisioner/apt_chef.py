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
from collections import namedtuple

from aminator.plugins.provisioner.apt import AptProvisionerPlugin
from aminator.util.linux import command
from aminator.util.linux import Chroot
from aminator.config import conf_action

__all__ = ('AptChefProvisionerPlugin',)
log = logging.getLogger(__name__)

CommandResult = namedtuple('CommandResult', 'success result')
CommandOutput = namedtuple('CommandOutput', 'std_out std_err')


class AptChefProvisionerPlugin(AptProvisionerPlugin):
    """
    AptChefProvisionerPlugin takes the majority of its behavior from BaseLinuxProvisionerPlugin
    See BaseLinuxProvisionerPlugin for details
    """
    _name = 'apt_chef'

    def add_plugin_args(self):
        context = self._config.context
        chef_config = self._parser.add_argument_group(title='Chef Solo Options',
                                                      description='Options for the chef solo provisioner')

        chef_config.add_argument('-j', '--json-attributes', dest='json',
                                 help='Chef JSON file (the same as running chef-solo -j)',
                                 action=conf_action(config=context.chef))
        chef_config.add_argument('-o', '--override-runlist', dest='override',
                                 help='Run this comma-separated list of items (the same as running chef-solo -o)',
                                 action=conf_action(config=context.chef))

    def _store_package_metadata(self):
        # Pass thru to the AptProvisioner method, but using our configs
        # since there isn't a package to get this info from, we'll need to be told
        # this stuff.  I'm thinking we could add it to the json file which is 
        # name = cookbook/role name
        # version = cookbook version
        # hopefully auto-generated from Jenkins


        context = self._config.context
        context.package.attributes = {'name': context.chef.json, 'version': 0.1, 'release': 0}

    def provision(self):
        context = self._config.context

        # for simple chef run, we need a json file (or -o?) tell what recipes to execute
        # - JSON file
        #    - solo.rb
        #    next steps:
        #    - load JSON from URL
        #    - support -o
        #    - copy in cookbooks?

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


class ChefNode(object):
    def __init__(self, name, description, version, release,
                 change, bug_id, build_job, built_by, build_date,
                 build_number, build_id, run_list):

        self.name = name
        self.description = description
        self.version = version
        self.release = release
        self.change = change
        self.bug_id = bug_id
        self.build_job = build_job
        self.built_by = built_by
        self.build_date = build_date
        self.build_number = build_number
        self.build_id = build_id
        self.run_list = run_list

    def object_decoder(self, obj):
        if '__type__' in obj and obj['__type__'] == 'ChefNode':
            return ChefNode(obj['name'], obj['description'], obj['version'],
                            obj['release'], obj['change'], obj['bug-id'], obj['build-job'],
                            obj['built-by'], obj['build-date'], obj['build-number'], obj['build-id'])
        return obj


@command()
def chef_solo(chef_dir, chef_json):
    # If run list is not specific, dont override it on the command line
    # if runlist:
    #     return 'chef-solo -j /tmp/node.json -c /tmp/solo.rb -o {0}'.format(runlist)
    # else:
    log.debug('Preparing to run chef-solo {0}'.format(chef_json))
    return 'chef-solo -j {0}/{1} -c {0}/solo.rb'.format(chef_dir, chef_json)
