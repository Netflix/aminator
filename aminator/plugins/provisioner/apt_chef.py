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
    Chef provisioner for debian family hosts

    Currently, it expects the Chef recipes to be pre-installed in the chef_dir so that the
    execution of this plugin can simply be triggered by supplying the usual chef-solo JSON node
    file.

    The JSON file (which is assumed to be the package_spec) is required as it will contain the recipes/roles to execute
    as well as the metadata we need for tagging since we won't be able to query a package for that data.

    TODOs:
        * -r equivalent which will enable amination using a tar.gz recipe file (file or http).
        * install chef from file or http for cases where we may be on a Chef-less install (can skip building a Base)


        https://opscode-omnibus-packages.s3.amazonaws.com/ubuntu/11.04/x86_64/chef_10.26.0-1.ubuntu.11.04_amd64.deb
"""
import logging
from collections import namedtuple
import json

from aminator.plugins.provisioner.apt import AptProvisionerPlugin, dpkg_install
from aminator.util import download_file
from aminator.util.linux import command
from aminator.util.linux import Chroot
from aminator.config import conf_action

__all__ = ('AptChefProvisionerPlugin',)
log = logging.getLogger(__name__)

CommandResult = namedtuple('CommandResult', 'success result')
CommandOutput = namedtuple('CommandOutput', 'std_out std_err')


class AptChefProvisionerPlugin(AptProvisionerPlugin):
    """
    AptChefProvisionerPlugin takes the majority of its behavior from AptProvisionerPlugin
    See AptProvisionerPlugin for details
    """
    _name = 'apt_chef'

    def add_plugin_args(self):
        context = self._config.context
        chef_config = self._parser.add_argument_group(title='Chef Solo Options',
                                                      description='Options for the chef solo provisioner')

        chef_config.add_argument('-u', '--recipe-url', dest='recipe_url',
                                 help='URL to tar.gz containing recipes (see chef-solo -r)',
                                 action=conf_action(config=context.chef))
        chef_config.add_argument('-i', '--install-chef', dest='chef_package_url',
                                 help='Install chef-solo from URL)',
                                 action=conf_action(config=context.chef))

    def _get_chef_json_full_path(self):
        return self._config.context.chef.dir + '/' + self._config.context.chef.json.lstrip('/')

    def _store_package_metadata(self):
        """
        these values come from the chef JSON node file since we can't query the package for these attributes
        """

        context = self._config.context
        log.debug('processing chef_json file {0} for package metadata'.format(self._get_chef_json_full_path()))
        with open(self._get_chef_json_full_path()) as chef_json_file:
            chef_json = json.load(chef_json_file)
            log.debug(
                'metadata attrs name=[{0}], version=[{1}], release=[{2}], build_job=[{3}], build_number=[{4}]'.format(
                    chef_json['name'], chef_json['version'], chef_json['release'], chef_json['build_job'],
                    chef_json['build_number']))

        context.package.attributes = {'name': chef_json['name'],
                                      'version': chef_json['version'],
                                      'release': chef_json['release'],
                                      'Build-Job': chef_json['build_job'],
                                      'Build-Number': chef_json['build_number']}

    def provision(self):

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

        # copy the JSON file to chef_dir
        if not self._stage_pkg():
            log.critical('failed to stage {0}'.format(context.package.arg))
            return False

        # if install chef, copy the deb to the volume

        with Chroot(self._mountpoint):
            log.debug('Inside chroot')

            # install chef if needed
            if context.chef.chef_package_url is not None:
                log.debug('prepping target dir {0}'.format(context.chef.dir))
                mkdirs(context.chef.dir)
                log.debug('preparing to download {0} to {1}'.format(context.chef.chef_package_url, context.chef.dir))
                download_file(context.chef.chef_package_url, context.chef.dir, context.package.get('timeout', 1))
                # get the package name so we can dpkg -i on it
                if context.chef.chef_package_url.stastartswith('http://'):
                    chef_package_name = context.chef.chef_package_url.split('/')[-1]
                else:
                    chef_package_name = context.chef.chef_package_url
                log.debug('preparing to do a dpkg -i {0}'.format(chef_package_name))
                dpkg_install(chef_package_name)

            log.debug('Preparing to run chef-solo')
            result = chef_solo(context.chef.dir, context.chef.json, context.chef.recipe_url)
            if not result.success:
                log.critical('chef-solo run failed: {0.std_err}'.format(result.result))
                return False

            self._store_package_metadata()

        log.debug('Exited chroot')

        log.info('Provisioning succeeded!')

        return True


class ChefNode(object):
    """
    Provide a convenient object mapping from a JSON string for a Chef JSON node
    """

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
                            obj['release'], obj['change'], obj['bug-id'], obj['build_job'],
                            obj['built_by'], obj['build_date'], obj['build_number'], obj['build_id'], obj['run_list'])
        return obj


@command()
def mkdirs(chef_dir):
    return 'mkdir -p {0}'.format(chef_dir)

@command()
def chef_solo(chef_dir, chef_json, chef_recipe_url=None):

    if chef_recipe_url is None:
        # we've have recipes pre-installed in chef_dir
        log.debug('Preparing to run chef-solo -j {0}/{1} -c {0}/solo.rb'.format(chef_dir, chef_json))
        return 'chef-solo -j {0}/{1} -c {0}/solo.rb'.format(chef_dir, chef_json)
    else:
        log.debug('Preparing to run chef-solo -j {0}/{1} -c {0}/solo.rb'.format(chef_dir, chef_json))
        return 'chef-solo -j {0}/{1} -r {2}'.format(chef_dir, chef_json, chef_recipe_url)

