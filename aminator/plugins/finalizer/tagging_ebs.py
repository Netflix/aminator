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
aminator.plugins.finalizer.tagging_ebs
======================================
ebs tagging image finalizer
"""
import logging

from aminator.config import conf_action
from aminator.plugins.finalizer.base import BaseFinalizerPlugin


__all__ = ('TaggingEBSFinalizerPlugin',)
log = logging.getLogger(__name__)


class TaggingEBSFinalizerPlugin(BaseFinalizerPlugin):
    _name = 'tagging_ebs'

    def __init__(self, *args, **kwargs):
        super(TaggingEBSFinalizerPlugin, self).__init__(*args, **kwargs)

    @property
    def enabled(self):
        return super(TaggingEBSFinalizerPlugin, self).enabled

    @enabled.setter
    def enabled(self, enable):
        super(TaggingEBSFinalizerPlugin, self).enabled = enable

    @property
    def entry_point(self):
        return super(TaggingEBSFinalizerPlugin, self).entry_point

    @property
    def name(self):
        return super(TaggingEBSFinalizerPlugin, self).name

    @property
    def full_name(self):
        return super(TaggingEBSFinalizerPlugin, self).full_name

    def configure(self, config, parser, *args, **kwargs):
        super(TaggingEBSFinalizerPlugin, self).configure(config, parser)

    def add_plugin_args(self):
        tagging = self.parser.add_argument_group(title='AMI Tagging and Naming',
                                                 description='Tagging and naming options for the resultant AMI')
        tagging.add_argument('-n', '--name', dest='name', action=conf_action(self.config.context.ami),
                             help='name of resultant AMI (default package_name-version-release-arch-yyyymmddHHMM-ebs')
        tagging.add_argument('-s', '--suffix', dest='suffix', action=conf_action(self.config.context.ami),
                             help='suffix of ami name, (default yyyymmddHHMM)')
        creator_help = 'The user who is aminating. The resultant AMI will receive a creator tag w/ this user'
        tagging.add_argument('-c', '--creator', dest='creator', action=conf_action(self.config.context.ami),
                             help=creator_help)

    def load_plugin_config(self, *args, **kwargs):
        super(TaggingEBSFinalizerPlugin, self).load_plugin_config(*args, **kwargs)

    def finalize(self, volume):
        return True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, trace):
        return False

    def __call__(self, cloud):
        self.cloud = cloud
        return self
