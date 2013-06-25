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
import logging

import json

from aminator.config import Config

from aminator.plugins.provisioner.apt_chef import AptChefProvisionerPlugin

log = logging.getLogger(__name__)
console = logging.StreamHandler()
# add the handler to the root logger
logging.getLogger('').addHandler(console)


class TestAptChefProvisionerPlugin(object):

    def setup_method(self, method):
        self.chef_provisioner = AptChefProvisionerPlugin()
        self.chef_provisioner._config = Config()
        self.chef_provisioner._config.context = Config()
        self.chef_provisioner._config.context.chef = Config()
        self.chef_provisioner._config.context.package = Config()
        self.chef_provisioner._config.pkg_attributes = ['name', 'version', 'release', 'build_job', 'build_number']
        self.chef_provisioner._config.context.chef.dir = "./tests"
        self.chef_provisioner._config.context.chef.json = "test_chef_node.json"

    def test_parse_json(self):

        # given a JSON doc, what's the name, version, release string, etc
        # this is more a direct test of the ChefJSON mapping

        with open(self.chef_provisioner._get_chef_json_full_path()) as chef_json_file:
            my_json = json.load(chef_json_file)
        assert "helloworld" == my_json['name']
        assert "APP-helloworld" == my_json['build_job']
        assert "1.0" == my_json['version']
        assert "277" == my_json['release']
        assert "33a9d1cac7686c8a46c1f330add2e8d36850fd15" == my_json['change']
        assert isinstance(my_json['run_list'], list)
        assert "recipe[helloworld]" == my_json['run_list'][0]

    def test_metadata(self):
        self.chef_provisioner._store_package_metadata()
        assert "helloworld" == self.chef_provisioner._config.context.package.attributes['name']
        assert "1.0" == self.chef_provisioner._config.context.package.attributes['version']
        assert "277" == self.chef_provisioner._config.context.package.attributes['release']
        assert "APP-helloworld" == self.chef_provisioner._config.context.package.attributes['build_job']
        assert "277" == self.chef_provisioner._config.context.package.attributes['build_number']
