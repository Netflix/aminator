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
from datetime import datetime

from aminator.config import conf_action
from aminator.plugins.finalizer.base import BaseFinalizerPlugin


__all__ = ('TaggingEBSFinalizerPlugin',)
log = logging.getLogger(__name__)


class TaggingEBSFinalizerPlugin(BaseFinalizerPlugin):
    _name = 'tagging_ebs'

    def add_plugin_args(self):
        context = self._config.context
        tagging = self._parser.add_argument_group(title='AMI Tagging and Naming',
                                                  description='Tagging and naming options for the resultant AMI')
        tagging.add_argument('-n', '--name', dest='name', action=conf_action(context.ami),
                             help='name of resultant AMI (default package_name-version-release-arch-yyyymmddHHMM-ebs')
        tagging.add_argument('-s', '--suffix', dest='suffix', action=conf_action(context.ami),
                             help='suffix of ami name, (default yyyymmddHHMM)')
        creator_help = 'The user who is aminating. The resultant AMI will receive a creator tag w/ this user'
        tagging.add_argument('-c', '--creator', dest='creator', action=conf_action(context.ami),
                             help=creator_help)

    def _set_metadata(self):
        context = self._config.context
        config = self._config.plugins[self.full_name]

        creator = context.ami.get('creator',
                                  config.get('creator',
                                             'aminator'))
        context.tags.ami.creator = creator
        context.tags.snapshot.creator = creator

        package_name = context.package.name
        package_version = context.package.version
        package_release = context.package.release
        arch = context.baseami.architecture

        suffix = context.ami.get(suffix, None)
        if not suffix:
            context.ami.suffix_format.format(datetime.utcnow())

        name = context.ami.get('name', None)
        if not name:
            name_metadata = {
                'package_name': package_name,
                'version': package_version,
                'release': package_release,
                'arch': arch,
                'suffix': suffix,
            }
            default_name = config.name_format.format(**name_metadata)
            name = default_name

        ami_name = '{0}-ebs'.format(name)

        context.ami.name = ami_name
        context.snapshot.name = name

        baseami_name = context.baseami.name
        baseami_id = context.baseami.id
        baseami_version = context.baseami.tags.get('base_ami_version', '')

        description_metadata = {
            'name': name,
            'arch': arch,
            'ancestor_name': baseami_name,
            'ancestor_id': baseami_id,
            'ancestor_version': baseami_version,
            }
        default_description = config.description_format.format(**description_metadata)
        description = context.snapshot.get('description', default_description)
        context.ami.description = description
        context.snapshot.description = description

    def _snapshot_volume(self):
        if not self._cloud.create_snapshot():
            return False

    def _register_image(self, block_device_map=None, root_device=None):
        config = self.config.plugins[self.full_name]
        if block_device_map is None:
            block_device_map = config.default_block_device_map
        if root_device is None:
            root_device = config.default_root_device
        if not self._cloud.register_image(block_device_map):
            return False

    def _add_tags(self):
        pass

    def finalize(self):

        self._set_metadata()

        if not self._snapshot_volume():
            log.critical('Error snapshotting volume')
            return False

        if not self._register_image():
            log.critical('Error registering image')
            return False

        if not self._add_tags():
            log.error('Error adding tags')
            return False

        log.info('Image registered and tagged')
        return True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, trace):
        return False

    def __call__(self, cloud):
        self._cloud = cloud
        return self
