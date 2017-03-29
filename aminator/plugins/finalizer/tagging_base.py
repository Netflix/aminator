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
aminator.plugins.finalizer.tagging_base
======================================
base tagging image finalizer
"""
import logging
from datetime import datetime
import abc

from os import environ
from aminator.config import conf_action
from aminator.exceptions import FinalizerException
from aminator.plugins.finalizer.base import BaseFinalizerPlugin

__all__ = ('TaggingBaseFinalizerPlugin',)
log = logging.getLogger(__name__)


class TaggingBaseFinalizerPlugin(BaseFinalizerPlugin):
    _name = 'tagging_base'

    def add_plugin_args(self):
        context = self._config.context
        tagging = self._parser.add_argument_group(title='AMI Tagging and Naming', description='Tagging and naming options for the resultant AMI')
        tagging.add_argument('-s', '--suffix', dest='suffix', action=conf_action(context.ami), help='suffix of ami name, (default yyyymmddHHMM)')
        creator_help = 'The user who is aminating. The resultant AMI will receive a creator tag w/ this user'
        tagging.add_argument('-c', '--creator', dest='creator', action=conf_action(context.ami), help=creator_help)
        tagging.add_argument('--vm-type', dest='vm_type', choices=["paravirtual", "hvm"], action=conf_action(context.ami), help='virtualization type to register image as')
        tagging.add_argument('--enhanced-networking', dest='enhanced_networking', action=conf_action(context.ami, action='store_true'), help='enable enhanced networking (SR-IOV)')
        tagging.add_argument('--ena-networking', dest='ena_networking', action=conf_action(context.ami, action='store_true'), help='enable elastic network adapter support (ENA)')
        tagging.add_argument('--arch', dest='architecture', choices=["i386", "x86_64"], action=conf_action(context.ami), help='architecture to register image as')
        return tagging

    def _set_metadata(self):
        context = self._config.context
        config = self._config.plugins[self.full_name]

        log.debug('Populating snapshot and ami metadata for tagging and naming')
        creator = context.ami.get('creator', config.get('creator', 'aminator'))
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

        for tag in config.tag_formats:
            try:
                context.ami.tags[tag] = config.tag_formats[tag].format(**metadata)
                context.snapshot.tags[tag] = config.tag_formats[tag].format(**metadata)
            except KeyError as e:
                errstr = 'Tag format requires information not available in package metadata: {0}'.format(e.message)
                log.warn(errstr)
                log.debug(errstr, exc_info=True)
                # in case someone uses a tag format based on metadata not available
                # in this package
                continue

        default_description = config.description_format.format(**metadata)
        description = context.snapshot.get('description', default_description)
        context.ami.description = description
        context.snapshot.description = description

    def _add_tags(self, resources):
        context = self._config.context
        context.ami.tags.creation_time = '{0:%F %T UTC}'.format(datetime.utcnow())
        for resource in resources:
            try:
                self._cloud.add_tags(resource)
            except FinalizerException:
                errstr = 'Error adding tags to {0}'.format(resource)
                log.error(errstr)
                log.debug(errstr, exc_info=True)
                return False
            log.info('Successfully tagged {0}'.format(resource))
        log.info('Successfully tagged objects')
        return True

    def _log_ami_metadata(self):
        context = self._config.context
        for attr in ('id', 'name', 'description', 'kernel_id', 'ramdisk_id', 'virtualization_type',):
            log.info('{0}: {1}'.format(attr, getattr(context.ami.image, attr)))
        for tag_name, tag_value in context.ami.image.tags.iteritems():
            log.info('Tag {0} = {1}'.format(tag_name, tag_value))

    @abc.abstractmethod
    def finalize(self):
        """ finalize an image """

    def __enter__(self):
        context = self._config.context
        if context.ami.get("suffix", None):
            environ["AMINATOR_AMI_SUFFIX"] = context.ami.suffix
        if context.ami.get("creator", None):
            environ["AMINATOR_CREATOR"] = context.ami.creator
        if context.ami.get("vm_type", None):
            environ["AMINATOR_VM_TYPE"] = context.ami.vm_type
        if context.ami.get("enhanced_networking", None):
            environ["AMINATOR_ENHANCED_NETWORKING"] = str(int(context.ami.enhanced_networking))
        if context.ami.get("ena_networking", None):
            environ["AMINATOR_ENA_NETWORKING"] = str(int(context.ami.ena_networking))

        if context.ami.get("enhanced_networking", False):
            if context.ami.get("vm_type", "paravirtual") != "hvm":
                raise ValueError("--enhanced-networking requires --vm-type hvm")

        if context.ami.get("ena_networking", False):
            if context.ami.get("vm_type", "paravirtual") != "hvm":
                raise ValueError("--ena-networking requires --vm-type hvm")

        return self

    def __exit__(self, exc_type, exc_value, trace):
        if exc_type:
            log.debug('Exception encountered in tagging base finalizer context manager',
                      exc_info=True)
        return False

    def __call__(self, cloud):
        self._cloud = cloud
        return self
