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
        # self.config.plugins = Config()
        self.chef_provisioner._config.context = Config()
        self.chef_provisioner._config.context.chef = Config()
        self.chef_provisioner._config.context.package = Config()
        self.chef_provisioner._config.context.package.attributes = Config()
        # self.config.context.chef.json = "test_chef_node.json"
        #self.chef_provisioner._config.context.chef.json = "/Users/kvick/Projects/github/netflix/aminator/aminator-chef/tests/test_chef_node.json"
        self.chef_provisioner._config.context.chef.json = "test_chef_node.json"
        self.chef_provisioner._mountpoint = '/Users/kvick/Projects/github/netflix/aminator/aminator-chef/tests'

    def test_parse_json(self):

        # given a JSON doc, what's the name, version, release string

        with open(self.chef_provisioner._get_chef_json_full_path()) as chef_json_file:
            my_json = json.load(chef_json_file)
        assert "mimir" == my_json['name']
        assert "WE-WAPP-mimir" == my_json['build_job']
        assert "1.0" == my_json['version']
        assert "277" == my_json['release']
        assert "33a9d1cac7686c8a46c1f330add2e8d36850fd15" == my_json['change']
        assert isinstance (my_json['run_list'], list)
        assert "recipe[engtools::mimir]" == my_json['run_list'][0]


    def test_metadata(self):
        self.chef_provisioner._store_package_metadata()
        # context.package.attributes = {'name': context.chef.json, 'version': 0.1, 'release': 0}
        # assert "mimird" == self.chef_provisioner._config.context.chef.json.name
        assert "1.0" == self.chef_provisioner._config.context.package.attributes['version']
        assert "277" == self.chef_provisioner._config.context.package.attributes['release']
