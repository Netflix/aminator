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
aminator.plugins.finalizer.tagging_ebs_euca
======================================
ebs tagging euca image finalizer
"""
import logging
from datetime import datetime

from aminator.config import conf_action
from aminator.exceptions import FinalizerException
from aminator.plugins.finalizer.base import BaseFinalizerPlugin
from aminator.util.linux import sanitize_metadata


__all__ = ('TaggingEBSEucaFinalizerPlugin',)
log = logging.getLogger(__name__)


class TaggingEBSEucaFinalizerPlugin(BaseFinalizerPlugin):
    _name = 'tagging_ebs_euca'

    def add_plugin_args(self):
        context = self._config.context
        tagging = self._parser.add_argument_group(title='AMI Tagging and Naming',
                                                  description='Tagging and naming options for the resultant AMI')
        #tagging.add_argument('-n', '--name', dest='name', action=conf_action(context.ami),
        #                     help='name of resultant AMI (default package_name-version-release-arch-yyyymmddHHMM-ebs')
        #tagging.add_argument('-s', '--suffix', dest='suffix', action=conf_action(context.ami),
        #                     help='suffix of ami name, (default yyyymmddHHMM)')
        #creator_help = 'The user who is aminating. The resultant AMI will receive a creator tag w/ this user'
        #tagging.add_argument('-c', '--creator', dest='creator', action=conf_action(context.ami),
        #                     help=creator_help)

    def _set_metadata(self):
        context = self._config.context
        config = self._config.plugins[self.full_name]

        log.debug('Populating snapshot and ami metadata for tagging and naming')
        creator = context.ami.get('creator',
                                  config.get('creator',
                                             'aminator'))
        context.ami.tags.creator = creator
        context.snapshot.tags.creator = creator

        metadata = context.package.attributes
        metadata['arch'] = context.base_ami.architecture
        metadata['base_ami_name'] = context.base_ami.name
        metadata['base_ami_id'] = context.base_ami.id
        metadata['base_ami_version'] = context.base_ami.tags.get('base_ami_version', '')

        suffix = context.ami.get('suffix', None)
        if not suffix:
            suffix = config.suffix_format.format(datetime.utcnow())

        metadata['suffix'] = suffix

        ami_name = context.ami.get('name', None)
        if not ami_name:
            ami_name = config.name_format.format(**metadata)

        context.ami.name = sanitize_metadata('{0}-ebs'.format(ami_name))

        for tag in config.tag_formats:
            context.ami.tags[tag] = config.tag_formats[tag].format(**metadata)
            context.snapshot.tags[tag] = config.tag_formats[tag].format(**metadata)

        default_description = config.description_format.format(**metadata)
        description = context.snapshot.get('description', default_description)
        context.ami.description = description
        context.snapshot.description = description

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

    def _add_tags(self):
        context = self._config.context
        context.ami.tags.creation_time = '{0:%F %T UTC}'.format(datetime.utcnow())
        for resource in ('snapshot', 'ami'):
            try:
                self._cloud.add_tags(resource)
            except FinalizerException, e:
                log.exception('Error adding tags to {0}'.format(resource))
                return False
            log.info('Successfully tagged {0}'.format(resource))
        else:
            log.info('Successfully tagged objects')
            return True

    def _log_ami_metadata(self):
        context = self._config.context
        for attr in ('id', 'name', 'description', 'kernel_id', 'ramdisk_id', 'virtualization_type',):
            log.info('{0}: {1}'.format(attr, getattr(context.ami.image, attr)))
        for tag_name, tag_value in context.ami.image.tags.iteritems():
            log.info('Tag {0} = {1}'.format(tag_name, tag_value))

    def finalize(self):
        log.info('Finalizing image')
        self._set_metadata()

        if not self._snapshot_volume():
            log.critical('Error snapshotting volume')
            return False

        if not self._register_image():
            log.critical('Error registering image')
            return False

        if not self._add_tags():
            log.critical('Error adding tags')
            return False

        log.info('Image registered and tagged')
        self._log_ami_metadata()
        return True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, trace):
        return False

    def __call__(self, cloud):
        self._cloud = cloud
        return self
