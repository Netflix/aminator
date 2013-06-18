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

from aminator.plugins.provisioner.apt_chef import AptChefProvisionerPlugin, ChefNode

log = logging.getLogger(__name__)
console = logging.StreamHandler()
# add the handler to the root logger
logging.getLogger('').addHandler(console)


class TestAptChefProvisionerPlugin(object):

    def test_parse_json(self):

        # given a JSON doc, what's the name, version, release string
        test_json = """
    {
        "__type__": "ChefNode",
        "name": "mimir",
        "description": "Continuous Delivery Console",
        "version": "1.0",
        "release": "277",
        "Change": "33a9d1cac7686c8a46c1f330add2e8d36850fd15",
        "Bug-Id": "",
        "Build-Job": "WE-WAPP-mimir",
        "Built-By": "builds",
        "Build-Date": "2013-06-14_16:22:24",
        "Build-Number": "277",
        "Build-Id": "2013-06-12_09-22-21",
        "run_list": [
            "recipe[engtools::mimir]",
            "recipe[engtools::foo]"
            ],
        "default_attributes": {
            "mimir": {
                "server": {
                    "home": "/var/lib/mimir",
                    "war_checksum": "7e676062231f6b80b60e53dc982eb89c36759bdd2da7f82ad8b35a002a36da9a"
                }
            }
        }
    }
    """

        my_json = json.loads(test_json)
        assert "mimir" == my_json['name']
        assert "1.0" == my_json['version']
        assert "277" == my_json['release']
        assert "33a9d1cac7686c8a46c1f330add2e8d36850fd15" == my_json['Change']
        assert isinstance (my_json['run_list'], list)
        assert "recipe[engtools::foo]" == my_json['run_list'][1]
        # assert "WE-WAPP-mimir" == my_json['build_job']

