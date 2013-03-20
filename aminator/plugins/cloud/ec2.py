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
aminator.plugins.cloud.ec2
==========================
ec2 cloud provider
"""
import logging

from boto.ec2 import connect_to_region
from boto.ec2.instance import Instance
from boto.utils import get_instance_metadata

from aminator.config import conf_action
from aminator.plugins.cloud.base import BaseCloudPlugin
from aminator.util.linux import device_prefix, native_block_device


__all__ = ('EC2Cloud',)
log = logging.getLogger(__name__)


class EC2CloudPlugin(BaseCloudPlugin):
    _name = 'ec2'

    def configure(self, config, parser):
        super(EC2CloudPlugin, self).configure(config, parser)

    def add_plugin_args(self):
        base_ami = self.parser.add_argument_group(title='Base AMI', description='EITHER AMI id OR name, not both!')
        base_ami_mutex = base_ami.add_mutually_exclusive_group(required=True)
        base_ami_mutex.add_argument('-b', '--base-ami-name', dest='base_ami_name',
                                    action=conf_action(config=self.config.context.ami),
                                    help='The name of the base AMI used in provisioning')
        base_ami_mutex.add_argument('-B', '--base-ami-id', dest='base_ami_id',
                                    action=conf_action(config=self.config.context.ami),
                                    help='The id of the base AMI used in provisioning')
        cloud = self.parser.add_argument_group(title='EC2 Options', description='EC2 Connection Information')
        cloud.add_argument('--ec2-region', dest='region', help='EC2 region (default: us-east-1)',
                           action=conf_action(config=self.config.context.cloud))
        cloud.add_argument('--boto-secure', dest='is_secure',  help='Connect via https',
                           action=conf_action(config=self.config.context.cloud, action='store_true'))
        cloud.add_argument('--boto-debug', dest='boto_debug', help='Boto debug output',
                           action=conf_action(config=self.config.context.cloud, action='store_true'))

    def connect(self, **kwargs):
        if not self._connection:
            log.info('Connecting to EC2')
            self._connect(**kwargs)
            return
        log.warn('Already connected to EC2')

    def _connect(self, **kwargs):
        cloud_config = self.config.plugins[self.full_name]
        region = cloud_config.region
        log.debug('Establishing boto connection to region: {0}'.format(region))

        if cloud_config.boto_debug:
            from aminator.config import log_per_package
            log_per_package(self.config, 'boto')
            kwargs['debug'] = 1
            log.debug('Boto debug logging enabled')
        else:
            logging.getLogger('boto').setLevel(logging.INFO)
        kwargs['is_secure'] = cloud_config.is_secure
        self._connection = connect_to_region(region, **kwargs)
        log.info('Aminating in region {0}'.format(region))

    def attach_volume_to_instance(self, blockdevice):
        pass

    def detach_volume_from_instance(self):
        pass

    def register_image(self):
        pass

    def attached_block_devs(self, native_device_prefix):
        self._instance_info.update()
        if device_prefix(self._instance_info.block_device_mapping.keys()[0]) != native_device_prefix:
            return dict((native_block_device(dev, native_device_prefix), mapping)
                        for (dev, mapping) in enumerate(self._instance_info.block_device_mapping))
        return self._instance_info.block_device_mapping

    def resolve_baseami(self):
        log.info('Resolving base AMI')
        context = self.config.context
        cloud_config = self.config.plugins[self.full_name]
        try:
            ami_id = context.ami.get('base_ami_name', cloud_config.get('base_ami_name', None))
            if ami_id is None:
                ami_id = context.ami.get('base_ami_id', cloud_config.get('base_ami_id', None))
                if ami_id is None:
                    raise RuntimeError('Must configure or provide either a base ami name or id')
                else:
                    context.ami['ami_id'] = ami_id
                    log.info('looking up base AMI with ID {0}'.format(ami_id))
                    baseami = self._connection.get_all_images(image_ids=[ami_id])[0]
            else:
                log.info('looking up base AMI with name {0}'.format(ami_id))
                baseami = self._connection.get_all_images(filters={'name': ami_id})[0]
        except IndexError:
            raise RuntimeError('Could not locate base AMI with identifier: {0}'.format(ami_id))
        log.info('Successfully resolved {0.name}({0.id})'.format(baseami))
        context['base_ami'] = baseami

    def __enter__(self):
        self.connect()
        self.resolve_baseami()
        self._instance_info = Instance(connection=self._connection)
        self._instance_info.id = get_instance_metadata()['instance-id']
        self._instance_info.update()

        return self

    def __exit__(self, typ, exc, trc):
        pass

    def __call__(self):
        return self
