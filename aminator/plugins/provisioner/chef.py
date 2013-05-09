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

"""
aminator.plugins.provisioner.chef
================================
chef provisioner
"""
import logging

from aminator.plugins.provisioner.base import BaseProvisionerPlugin
from aminator.util.linux import short_circuit_files, rewire_files

__all__ = ('ChefProvisionerPlugin',)
log = logging.getLogger(__name__)


class ChefProvisionerPlugin(BaseProvisionerPlugin):
    """
    ChefProvisionerPlugin allows you to use existing Chef recipes to manage OS and code
    """
    _name = 'chef'

    def provision(self):
        pass

    def __enter__(self):
        if not self._configure_chroot():
            raise VolumeException('Error configuring chroot')
        return self

    def __exit__(self, exc_type, exc_value, trace):
        if not self._teardown_chroot():
            raise VolumeException('Error tearing down chroot')
        return False
