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

    This plugin works by requiring a JSON file that contains the standard chef-solo node attributes.  To support
    the metadata that aminator adds to the finished AMI, we'll add some additional fields that will be set in the
    context by _store_package_metadata that will be used during the tagging finalizer (e.g. Jenkins job and build
    number)

    Since the package_arg is required by aminator we'll use it for the JSON file and works via http or a local file.
    Note, if specified locally, that file will be moved to the chroot and lost.

    This plugin will also allow you to install Chef omnibus from a URL.  Recipes can also be provided via http in
    a tar.gz.  This supports aminating on an EBS volume that doesn't have chef pre-installed.
"""
import json
import logging
import os.path
from collections import namedtuple

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
                                 help='URL to tar.gz containing recipes (see chef-solo -r)', default=None,
                                 action=conf_action(config=context.chef))
        chef_config.add_argument('-i', '--install-chef', dest='chef_package_url',
                                 help='Install chef-solo from URL', default=None,
                                 action=conf_action(config=context.chef))

    def _get_chef_json_full_path(self):
        """
        :return the fully qualified path of the JSON file in the chroot
        """
        return self._config.context.chef.dir + '/' + self._config.context.chef.json.lstrip('/')

    def _store_package_metadata(self):
        """
        save info for the AMI we're building in the context so that it can be incorporated into tags and the description
        during finalization. these values come from the chef JSON node file since we can't query the package for these
        attributes
        """

        context = self._config.context
        log.debug('processing chef_json file {0} for package metadata'.format(self._get_chef_json_full_path()))
        with open(self._get_chef_json_full_path()) as chef_json_file:
            chef_json = json.load(chef_json_file)
            log.debug(chef_json.dump)

        context.package.attributes = {}
        for x in self._config.pkg_attributes:
            context.package.attributes[x] = chef_json.get(x, None)

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
        context.package.dir = config.plugins[self.full_name].get('chef_dir', '/var/chef')

        context.chef.setdefault('dir', context.package.dir)

        # copy the JSON file to chef_dir in the chroot.  mkdirs in case we've never installed chef
        full_chef_dir_path = self._mountpoint + context.chef.dir
        log.debug('prepping chef_dir {0}'.format(full_chef_dir_path))
        mkdirs(full_chef_dir_path)

        if not self._stage_pkg():
            log.critical('failed to stage {0}'.format(context.package.arg))
            return False

        with Chroot(self._mountpoint):
            log.debug('Inside chroot')

            # install chef if needed
            if 'chef_package_url' in context.chef:
                log.debug('chef install selected')
                # get the package name so we can dpkg -i on it
                chef_package_name = os.path.basename(context.chef.chef_package_url)
                local_chef_package_file = context.chef.dir + '/' + chef_package_name
                log.debug('preparing to download {0} to {1}'.format(context.chef.chef_package_url,
                                                                    local_chef_package_file))
                download_file(context.chef.chef_package_url, local_chef_package_file,
                              context.package.get('timeout', 1), verify_https=context.get('verify_https', False))
                log.debug('preparing to do a dpkg -i {0}'.format(chef_package_name))
                dpkg_install(local_chef_package_file)

            log.debug('Preparing to run chef-solo')

            if 'recipe_url' in context.chef:
                result = chef_solo(context.chef.dir, context.package.file, context.chef.recipe_url)
            else:
                result = chef_solo(context.chef.dir, context.package.file, None)

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
        # we have recipes pre-installed in chef_dir
        log.debug('Preparing to run chef-solo -j {0}/{1} -c {0}/solo.rb'.format(chef_dir, chef_json))
        return 'chef-solo -j {0}/{1} -c {0}/solo.rb'.format(chef_dir, chef_json)
    else:
        log.debug('Preparing to run chef-solo -j {0}/{1} -r {2}'.format(chef_dir, chef_json, chef_recipe_url))
        return 'chef-solo -j {0}/{1} -r {2}'.format(chef_dir, chef_json, chef_recipe_url)

