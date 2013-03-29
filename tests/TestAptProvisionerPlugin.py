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
import os
from aminator.plugins.provisioner.apt import AptProvisionerPlugin


class TestAptProvisionerPlugin(object):

    def setup_method(self, method):
        self.plugin = AptProvisionerPlugin()
        self.plugin._mountpoint = "/tmp"
        self.full_path = self.plugin._mountpoint + "/" + AptProvisionerPlugin.POLICY_FILE_PATH + "/" + \
                         AptProvisionerPlugin.POLICY_FILE
        try:
            os.remove(self.full_path)
        except OSError:
            pass

    def test_disable_enable_service_startup(self):
        assert self.plugin._disable_service_startup()
        assert os.path.isfile(self.full_path)
        assert self.plugin._enable_service_startup()
        assert False == os.path.isfile(self.full_path)


