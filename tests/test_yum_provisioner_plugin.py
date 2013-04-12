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
from aminator.plugins.provisioner.yum import YumProvisionerPlugin
from aminator.config import Config

log = logging.getLogger(__name__)
console = logging.StreamHandler()
# add the handler to the root logger
logging.getLogger('').addHandler(console)

class TestYumProvisionerPlugin(object):

    def setup_method(self, method):
        self.config = Config()
        self.config.plugins = Config()
        self.config.plugins['aminator.plugins.provisioner.yum'] = self.config.from_file(yaml_file='yum_test.yml')

        self.plugin = YumProvisionerPlugin()
        self.plugin._config = self.config

    def test_deactivate_active_services(self):

        files = self.plugin._config.plugins['aminator.plugins.provisioner.yum'].get('short_circuit_files', [])

        if len(files) != 1:
            raise AttributeError("incorrect number of files specified.  found %d expected 1", len(files))

        filename = files[0]

        if not os.path.isdir(os.path.dirname(filename)):
            os.makedirs(os.path.dirname(filename))

        # cleanup
        if os.path.islink(filename):
            log.debug("removing %s", filename)
            os.remove(filename)

        with open(filename, 'w') as f:
            log.debug("writing %s", filename)
            f.write("test")
            log.debug("wrote %s", filename)

        assert self.plugin._deactivate_provisioning_service_block()
        assert True == os.path.islink('/tmp/sbin/service')
        assert self.plugin._activate_provisioning_service_block()
        assert False == os.path.islink('/tmp/sbin/service')
