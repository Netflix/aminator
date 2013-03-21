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
from boto.ec2.volume import Volume
from boto.exception import EC2ResponseError
from boto.utils import get_instance_metadata

from aminator.config import conf_action
from aminator.exceptions import VolumeException
from aminator.plugins.cloud.base import BaseCloudPlugin
from aminator.util import retry
from aminator.util.linux import device_prefix, native_block_device, os_node_exists


__all__ = ('EC2CloudPlugin',)
log = logging.getLogger(__name__)


class EC2CloudPlugin(BaseCloudPlugin):
    _name = 'ec2'

    def __init__(self, *args, **kwargs):
        super(EC2CloudPlugin, self).__init__(*args, **kwargs)

    @property
    def enabled(self):
        return super(EC2CloudPlugin, self).enabled

    @enabled.setter
    def enabled(self, enable):
        super(EC2CloudPlugin, self).enabled = enable

    @property
    def entry_point(self):
        return super(EC2CloudPlugin, self).entry_point

    @property
    def name(self):
        return super(EC2CloudPlugin, self).name

    @property
    def full_name(self):
        return super(EC2CloudPlugin, self).full_name

    def configure(self, *args, **kwargs):
        super(EC2CloudPlugin, self).configure(*args, **kwargs)

    def add_plugin_args(self, *args, **kwargs):
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

    def load_plugin_config(self, *args, **kwargs):
        super(EC2CloudPlugin, self).load_plugin_config(*args, **kwargs)

    def connect(self, **kwargs):
        if not self._connection:
            log.info('Connecting to EC2')
            self._connect(**kwargs)
            return
        log.warn('Already connected to EC2')

    def _connect(self, **kwargs):
        cloud_config = self.config.plugins[self.full_name]
        context = self.config.context
        self._instance_metadata = get_instance_metadata()
        region = context.get('region',
                             cloud_config.get('region', self._instance_metadata['placement']['availability-zone'][:-1]))
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

    @property
    def connection(self):
        return self._connection

    @property
    def instance(self):
        return self._instance_info

    @property
    def volume(self):
        return self._volume

    def allocate_base_volume(self, tag=True):
        cloud_config = self.config.plugins[self.full_name]
        context = self.config.context

        self._volume = Volume(connection=self._connection)

        rootdev = context.base_ami.block_device_mapping[context.base_ami.root_device_name]
        self.volume.id = self._connection.create_volume(size=rootdev.size, zone=self.instance.placement,
                                                        snapshot=rootdev.snapshot_id).id
        if tag:
            tags = {
                'purpose': cloud_config.get('tag_ami_purpose', 'amination'),
                'status': 'busy',
                'ami': context.base_ami.id,
                'ami-name': context.base_ami.name,
                'arch': context.base_ami.architecture,
            }
            self.connection.create_tags([self.volume.id], tags)
        self.volume.update()
        log.debug('Volume {0} created'.format(self.volume.id))

    @retry(VolumeException, tries=2, delay=1, backoff=2, logger=log)
    def attach_volume(self, blockdevice, tag=True):
        self.allocate_base_volume(tag=tag)
        # must do this as amazon still wants /dev/sd*
        ec2_device_name = blockdevice.replace('xvd', 'sd')
        log.debug('Attaching volume {0} to {1}:{2}({3})'.format(self.volume.id, self.instance.id, ec2_device_name,
                                                                blockdevice))
        self.volume.attach(self.instance.id, ec2_device_name)
        if not self.volume_attached(blockdevice):
            log.debug('{0} attachment to {1}:{2}({3}) timed out'.format(self.volume.id, self.instance.id,
                                                                        ec2_device_name, blockdevice))
            self.volume.add_tag('status', 'used')
            # trigger a retry
            raise VolumeException('Timed out waiting for {0} to attach to {1}:{2}'.format(self.volume.id,
                                                                                          self.instance.id,
                                                                                          blockdevice))
        log.debug('Volume {0} attached to {1}:{2}'.format(self.volume.id, self.instance.id, blockdevice))

    def volume_attached(self, blockdevice):
        try:
            self._volume_attached(blockdevice)
        except VolumeException:
            log.debug('Timed out waiting for volume {0} to attach to {1}:{2}'.format(self.volume.id,
                                                                                     self.instance.id, blockdevice))
            return False
        return True

    @retry(VolumeException, tries=10, delay=1, backoff=2, logger=log)
    def _volume_attached(self, blockdevice):
        status = self.volume.update()
        if status != 'in-use':
            raise VolumeException('Volume {0} not yet attached to {1}:{2}'.format(self.volume.id,
                                                                                  self.instance.id, blockdevice))
        elif not os_node_exists(blockdevice):
            raise VolumeException('{0} does not exist yet.'.format(blockdevice))
        else:
            return True

    def detach_volume(self, blockdevice):
        log.debug('Detaching volume {0} from {1}'.format(self.volume.id, self.instance.id))
        self.volume.detach()
        if not self._volume_detached(blockdevice):
            raise VolumeException('Time out waiting for {0} to detach from {1]'.format(self.volume.id,
                                                                                       self.instance.id))
        log.debug('Successfully detached volume {0} from {1}'.format(self.volume.id, self.instance.id))

    @retry(VolumeException, tries=7, delay=1, backoff=2, logger=log)
    def _volume_detached(self, blockdevice):
        status = self.volume.update()
        if status != 'available':
            raise VolumeException('Volume {0} not yet detached from {1}'.format(self.volume.id, self.instance.id))
        elif os_node_exists(blockdevice):
            raise VolumeException('Device node {0} still exists'.format(blockdevice))
        else:
            return True

    def delete_volume(self):
        log.debug('Deleting volume {0}'.format(self.volume.id))
        self.volume.delete()
        return self._volume_deleted()

    def _volume_deleted(self):
        try:
            self.volume.update()
        except EC2ResponseError, e:
            if e.code == 'InvalidVolume.NotFound':
                log.debug('Volume {0} successfully deleted'.format(self.volume.id))
                return True
            return False

    def is_stale_attachment(self, dev, prefix):
        log.debug('Checking for stale attachment. dev: {0}, prefix: {1}'.format(dev, prefix))
        if dev in self.attached_block_devices(prefix) and not os_node_exists(dev):
            log.debug('{0} is stale, rejecting'.format(dev))
            return True
        log.debug('{0} not stale, using'.format(dev))
        return False

    def register_image(self):
        pass

    def attached_block_devices(self, prefix):
        log.debug('Checking for currently attached block devices. prefix: {0}'.format(prefix))
        self.instance.update()
        if device_prefix(self.instance.block_device_mapping.keys()[0]) != prefix:
            return dict((native_block_device(dev, prefix), mapping)
                        for (dev, mapping) in self.instance.block_device_mapping.iteritems())
        return self.instance.block_device_mapping

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
        return False

    def __call__(self):
        return self
