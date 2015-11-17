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

from os import environ
from aminator.config import conf_action
from aminator.plugins.finalizer.tagging_base import TaggingBaseFinalizerPlugin
from aminator.util.linux import sanitize_metadata


__all__ = ('TaggingEBSFinalizerPlugin',)
log = logging.getLogger(__name__)


class TaggingEBSFinalizerPlugin(TaggingBaseFinalizerPlugin):
    _name = 'tagging_ebs'

    def add_plugin_args(self):
        tagging = super(TaggingEBSFinalizerPlugin, self).add_plugin_args()

        context = self._config.context
        tagging.add_argument('-n', '--name', dest='name', action=conf_action(context.ami), help='name of resultant AMI (default package_name-version-release-arch-yyyymmddHHMM-ebs')

    def _set_metadata(self):
        super(TaggingEBSFinalizerPlugin, self)._set_metadata()
        context = self._config.context
        config = self._config.plugins[self.full_name]
        metadata = context.package.attributes
        ami_name = context.ami.get('name', None)
        if not ami_name:
            ami_name = config.name_format.format(**metadata)

        context.ami.name = sanitize_metadata('{0}-ebs'.format(ami_name))

    def _snapshot_volume(self):
        log.info('Taking a snapshot of the target volume')
        if not self._cloud.snapshot_volume():
            return False
        log.info('Snapshot success')
        return True

    def _register_image(self, block_device_map=None, root_device=None):
        log.info('Registering image')
        config = self._config.plugins[self.full_name]
        if block_device_map is None:
            block_device_map = config.default_block_device_map
        if root_device is None:
            root_device = config.default_root_device
        if not self._cloud.register_image(block_device_map, root_device):
            return False
        log.info('Registration success')
        return True

    def finalize(self):
        log.info('Finalizing image')
        self._set_metadata()

        if not self._snapshot_volume():
            log.critical('Error snapshotting volume')
            return False

        if not self._register_image():
            log.critical('Error registering image')
            return False

        if not self._add_tags(['snapshot', 'ami']):
            log.critical('Error adding tags')
            return False

        log.info('Image registered and tagged')
        self._log_ami_metadata()
        return True

    def __enter__(self):
        context = self._config.context
        environ["AMINATOR_STORE_TYPE"] = "ebs"
        if context.ami.get("name", None):
            environ["AMINATOR_AMI_NAME"] = context.ami.name
        return super(TaggingEBSFinalizerPlugin, self).__enter__()
