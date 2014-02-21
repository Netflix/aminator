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
import os

from aminator.util.linux import keyval_parse, Response, CommandResult

from aminator.plugins.provisioner.apt import AptProvisionerPlugin
from aminator.config import Config
from collections import namedtuple

log = logging.getLogger(__name__)
console = logging.StreamHandler()
# add the handler to the root logger
logging.getLogger('').addHandler(console)


class TestAptProvisionerPlugin(object):

    def setup_method(self, method):
        self.config = Config()
        self.config.plugins = Config()

        # TODO: this is fragile as it may depend on the dir the tests were run from
        self.config.plugins['aminator.plugins.provisioner.apt'] = self.config.from_file(yaml_file='aminator/plugins/provisioner/default_conf/aminator.plugins.provisioner.apt.yml')

        log.info(self.config.plugins)
        self.plugin = AptProvisionerPlugin()

        self.plugin._config = self.config

        config = self.plugin._config.plugins['aminator.plugins.provisioner.apt']

        # use /tmp if not configured, ideally to use tempfile, but needs C build
        self.full_path = config.get('mountpoint', '/tmp') + "/" + \
                         config.get('policy_file_path', '/usr/sbin') + "/" + \
                         config.get('policy_file', 'policy-rc.d')

        self.plugin._mountpoint = config.get('mountpoint', '/tmp')

        # cleanup
        if os.path.isfile(self.full_path):
            os.remove(self.full_path)

    def test_disable_enable_service_startup(self):
        assert self.plugin._deactivate_provisioning_service_block()
        assert os.path.isfile(self.full_path)

        with open(self.full_path) as f:
            content = f.readlines()

        # remove whitespace and newlines
        content = map(lambda s: s.strip(), content)
        # also remove whitespace and newlines
        original_content = self.config.plugins['aminator.plugins.provisioner.apt'].get('policy_file_content').splitlines()

        assert original_content == content

        assert self.plugin._activate_provisioning_service_block()
        assert False == os.path.isfile(self.full_path)

    def test_metadata(self):
        """ test that given we get back the metadata we expect
            this first was a problem when the deb Description field had leading whitespace
            which caused the keys to contain leading whitespace
        """

        response = Response()
        response.std_out = """
  Package: helloWorld
  Source: helloWorld
  Version: 1374197704:1.0.0-h357.6ea8a16
  Section: None
  Priority: optional
  Architecture: all
  Provides: helloWorld
  Installed-Size: 102704
  Maintainer: someone@somewhere.org
  Description: helloWorld
   ----------
   Manifest-Version: 1.1
   Implementation-Vendor: Hello, Inc.
   Implementation-Title: helloWorld;1.0.0
   Implementation-Version: 1.0.0
   Label: helloWorld-1.0.0
   Built-By: builder
   Build-Job: JOB-helloWorld
   Build-Date: 2013-07-19_01:33:52
   Build-Number: 357
   Build-Id: 2013-07-18_18-24-53
   Change: 6ea8a16
"""
        package_query_result = CommandResult(True, response)
        result = parse_command_result(package_query_result)

        assert result['Build-Number'] == '357'
        assert result['Build-Job'] == 'JOB-helloWorld'

@keyval_parse()
def parse_command_result(data):
    return data
