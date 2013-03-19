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
aminator.plugins.provisioner.apt
================================
basic apt provisioner
"""
import logging

from aminator.plugins.provisioner.base import BaseProvisionerPlugin


__all__ = ('AptProvisionerPlugin',)
log = logging.getLogger(__name__)


class AptProvisionerPlugin(BaseProvisionerPlugin):
    _name = 'apt'

    def configure(self, config, parser):
        super(AptProvisionerPlugin, self).configure(config, parser)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, trace):
        pass

    def __call__(self, volume):
        self.volume = volume
        return self

    def provision(self):
        pass
