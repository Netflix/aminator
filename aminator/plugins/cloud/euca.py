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
aminator.plugins.cloud.euca
==========================
euca cloud provider
"""
import logging
from time import sleep
from boto.ec2.volume import Volume
from boto.exception import EC2ResponseError
from boto.regioninfo import RegionInfo
from boto.utils import get_instance_metadata, boto
from decorator import decorator
from aminator.config import conf_action
from aminator.exceptions import VolumeException
from aminator.plugins.cloud.ec2 import EC2CloudPlugin
from aminator.util import retry
from aminator.util.linux import device_prefix, native_block_device, command


__all__ = ('EucaCloudPlugin',)
log = logging.getLogger(__name__)


def registration_retry(ExceptionToCheck=(EC2ResponseError,), tries=3, delay=1, backoff=1, logger=None):
    """
    a slightly tweaked form of aminator.util.retry for handling retries on image registration
    """
    if logger is None:
        logger = log

    @decorator
    def _retry(f, *args, **kwargs):
        _tries, _delay = tries, delay
        total_tries = _tries
        args, kwargs = args, kwargs
        while _tries > 0:
            try:
                return f(*args, **kwargs)
            except ExceptionToCheck, e:
                if e.error_code == 'InvalidAMIName.Duplicate':
                    log.debug('Duplicate AMI Name {0}, retrying'.format(kwargs['name']))
                    attempt = abs(_tries - (total_tries + 1))
                    kwargs['name'] = kwargs.pop('name') + str(attempt)
                    log.debug('Trying name {0}'.format(kwargs['name']))
                    sleep(_delay)
                    _tries -= 1
                    _delay *= backoff
                else:
                    for (code, msg) in e.errors:
                        log.critical('EC2ResponseError: {0}: {1}.'.format(code, msg))
                        return False
        log.critical('Failed to register AMI')
        return False
    return _retry

@command()
def get_device(device):
    return "ls -1 " + device

class EucaCloudPlugin(EC2CloudPlugin):
    _name = 'euca'

    def add_plugin_args(self, *args, **kwargs):
        context = self._config.context
        cloud = self._parser.add_argument_group(title='EC2 Options', description='EC2 Connection Information')
        cloud.add_argument('--ec2-endpoint', dest='ec2_endpoint', help='EC2 endpoint  to connect to',
                           action=conf_action(config=context.cloud))

    def configure(self, config, parser):
        super(EucaCloudPlugin, self).configure(config, parser)
        host = config.context.web_log.get('host', False)
        if not host:
            md = get_instance_metadata()
            pub, ipv4 = 'public-hostname', 'local-ipv4'
            config.context.web_log['host'] = md[pub] if pub in md else md[ipv4]

    def connect(self, **kwargs):
        if self._connection:
            log.warn('Already connected to Euca')
        else:
            log.info('Connecting to Euca')
            self._connect(**kwargs)

    def _connect(self, **kwargs):
        cloud_config = self._config.plugins[self.full_name]
        context = self._config.context
        self._instance_metadata = get_instance_metadata()
        euca_path = "/services/Eucalyptus"
        euca_port = 8773
        ec2_region = RegionInfo()
        ec2_region.name = 'eucalyptus'
        ec2_region.endpoint = context.cloud.ec2_endpoint
        connection_args = { 'is_secure': False,
                            'debug': 0,
                            'port' : 8773,
                            'path' : euca_path,
                            'host' : context.cloud.ec2_endpoint,
                            'api_version': '2012-07-20',
                            'region': ec2_region }

        if float(boto.__version__[0:3]) >= 2.6:
            connection_args['validate_certs'] = False

        self._connection = boto.connect_ec2(**connection_args)

        log.info('Aminating in region {0}: http://{1}:{2}{3}'.format(ec2_region.name,
                                                                      context.cloud.ec2_endpoint,
                                                                      euca_port,
                                                                      euca_path))

    def allocate_base_volume(self, tag=True):
        cloud_config = self._config.plugins[self.full_name]
        context = self._config.context

        self._volume = Volume(connection=self._connection)

        rootdev = context.base_ami.block_device_mapping[context.base_ami.root_device_name]
        self._volume.id = self._connection.create_volume(size=rootdev.size, zone=self._instance.placement,
                                                         snapshot=rootdev.snapshot_id).id
        if not self._volume_available():
            log.critical('{0}: unavailable.')
            return False

        if tag:
            tags = {
                'purpose': cloud_config.get('tag_ami_purpose', 'amination'),
                'status': 'busy',
                'ami': context.base_ami.id,
                'ami-name': context.base_ami.name,
                'arch': context.base_ami.architecture,
            }
            self._connection.create_tags([self._volume.id], tags)
        self._volume.update()
        log.debug('Volume {0} created'.format(self._volume.id))

    @retry(VolumeException, tries=2, delay=1, backoff=1, logger=log)
    def attach_volume(self, blockdevice, tag=True):
        self.allocate_base_volume(tag=tag)
        # must do this as amazon still wants /dev/sd*
        ec2_device_name = blockdevice.replace('sd', 'vd')
        log.debug('Attaching volume {0} to {1}:{2}({3})'.format(self._volume.id, self._instance.id, ec2_device_name,
                                                                blockdevice))
        self._volume.attach(self._instance.id, ec2_device_name)
        attached_device = self.is_volume_attached(ec2_device_name)
        if attached_device != ec2_device_name:
            log.debug('{0} attachment to {1}:{2}({3}) timed out'.format(self._volume.id, self._instance.id,
                                                                        ec2_device_name, blockdevice))
            self._volume.add_tag('status', 'used')
            # trigger a retry
            raise VolumeException('Timed out waiting for {0} to attach to {1}:{2}'.format(self._volume.id,
                                                                                              self._instance.id,
                                                                                          blockdevice))
        log.debug('Volume {0} attached to {1}:{2}'.format(self._volume.id, self._instance.id, blockdevice))
        return blockdevice

    def is_volume_attached(self, ec2_device_name):
        try:
            attached_device = self._volume_attached(ec2_device_name)
        except VolumeException:
            log.debug('Timed out waiting for volume {0} to attach to {1}'.format(self._volume.id,
                                                                                     self._instance.id))
            return False
        return attached_device

    @retry(VolumeException, tries=10, delay=10, backoff=1, logger=log)
    def _volume_attached(self, ec2_device_name):
        status = self._volume.update()
        if status != 'in-use':
            raise VolumeException('Volume {0} not yet attached to {1}'.format(self._volume.id,
                                                                                  self._instance.id))
        elif not get_device(ec2_device_name).result.std_out:
            raise VolumeException('No change in device list yet. Unable to find device: {0}'.format(ec2_device_name))
        else:
            return ec2_device_name

    def register_image(self, block_device_map, root_block_device):
        context = self._config.context
        bdm = self._make_block_device_map(block_device_map, root_block_device)
        ami_metadata = {
            'name': context.ami.name,
            'description': context.ami.description,
            'block_device_map': bdm,
            'root_device_name': root_block_device,
            'kernel_id': context.base_ami.kernel_id,
            'ramdisk_id': context.base_ami.ramdisk_id,
            'architecture': context.base_ami.architecture
        }
        if not self._register_image(**ami_metadata):
            return False
        return True

    def attached_block_devices(self, prefix):
        log.debug('Checking for currently attached block devices. prefix: {0}'.format(prefix))
        self._instance.update()
        if device_prefix(self._instance.block_device_mapping.keys()[0]) != prefix:
            return dict((native_block_device(dev, prefix), mapping)
                        for (dev, mapping) in self._instance.block_device_mapping.iteritems())
        return self._instance.block_device_mapping
