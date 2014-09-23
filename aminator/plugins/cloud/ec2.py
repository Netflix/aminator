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
from time import sleep

from boto.ec2 import connect_to_region, EC2Connection
from boto.ec2.blockdevicemapping import BlockDeviceMapping, BlockDeviceType
from boto.ec2.image import Image
from boto.ec2.instance import Instance
from boto.ec2.volume import Volume
from boto.exception import EC2ResponseError
from boto.utils import get_instance_metadata
from decorator import decorator
from os import environ

from aminator.config import conf_action
from aminator.exceptions import FinalizerException, VolumeException
from aminator.plugins.cloud.base import BaseCloudPlugin
from aminator.util import retry
from aminator.util.linux import device_prefix, native_block_device, os_node_exists
from aminator.util.metrics import timer, raises, succeeds, lapse


__all__ = ('EC2CloudPlugin',)
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


class EC2CloudPlugin(BaseCloudPlugin):
    _name = 'ec2'

    def add_metrics(self, metric_base_name, cls, func_name):
        newfunc = succeeds("{0}.count".format(metric_base_name), self)(
            raises("{0}.error".format(metric_base_name), self)(
                timer("{0}.duration".format(metric_base_name), self)(
                    getattr(cls,func_name)
                )
            )
        )
        setattr(cls, func_name, newfunc)

    def __init__(self):
        super(EC2CloudPlugin,self).__init__()
        # wrap each of the functions so we can get timer and error metrics
        for ec2func in ["create_volume", "create_tags", "register_image", "get_all_images"]:
            self.add_metrics("aminator.cloud.ec2.connection.{0}".format(ec2func), EC2Connection, ec2func)
        for volfunc in ["add_tag", "attach", "create_snapshot", "delete", "detach", "update"]:
            self.add_metrics("aminator.cloud.ec2.volume.{0}".format(volfunc), Volume, volfunc)
        for imgfunc in ["update"]:
            self.add_metrics("aminator.cloud.ec2.image.{0}".format(imgfunc), Image, imgfunc)
        for insfunc in ["update"]:
            self.add_metrics("aminator.cloud.ec2.instance.{0}".format(insfunc), Instance, insfunc)

    def add_plugin_args(self, *args, **kwargs):
        context = self._config.context
        base_ami = self._parser.add_argument_group(title='Base AMI', description='EITHER AMI id OR name, not both!')
        base_ami_mutex = base_ami.add_mutually_exclusive_group(required=True)
        base_ami_mutex.add_argument('-b', '--base-ami-name', dest='base_ami_name',
                                    action=conf_action(config=context.ami),
                                    help='The name of the base AMI used in provisioning')
        base_ami_mutex.add_argument('-B', '--base-ami-id', dest='base_ami_id',
                                    action=conf_action(config=context.ami),
                                    help='The id of the base AMI used in provisioning')
        cloud = self._parser.add_argument_group(title='EC2 Options', description='EC2 Connection Information')
        cloud.add_argument('-r', '--region', dest='region', help='EC2 region (default: us-east-1)',
                           action=conf_action(config=context.cloud))
        cloud.add_argument('--boto-secure', dest='is_secure',  help='Connect via https',
                           action=conf_action(config=context.cloud, action='store_true'))
        cloud.add_argument('--boto-debug', dest='boto_debug', help='Boto debug output',
                           action=conf_action(config=context.cloud, action='store_true'))
        cloud.add_argument('-V', '--volume-id', dest='volume_id',
                           action=conf_action(config=context.ami),
                           help='The volume id already attached to the system')

    def configure(self, config, parser):
        super(EC2CloudPlugin, self).configure(config, parser)
        host = config.context.web_log.get('host', False)
        if not host:
            md = get_instance_metadata()
            pub, ipv4 = 'public-hostname', 'local-ipv4'
            config.context.web_log['host'] = md[pub] if pub in md else md[ipv4]

    def connect(self, **kwargs):
        if self._connection:
            log.warn('Already connected to EC2')
        else:
            log.info('Connecting to EC2')
            self._connect(**kwargs)

    def _connect(self, **kwargs):
        cloud_config = self._config.plugins[self.full_name]
        context = self._config.context
        self._instance_metadata = get_instance_metadata()
        instance_region = self._instance_metadata['placement']['availability-zone'][:-1]
        region = kwargs.pop('region',
                            context.get('region',
                                        cloud_config.get('region',
                                                         instance_region)))
        log.debug('Establishing connection to region: {0}'.format(region))

        context.cloud.setdefault('boto_debug', False)
        if context.cloud.boto_debug:
            from aminator.config import configure_datetime_logfile
            configure_datetime_logfile(self._config, 'boto')
            kwargs['debug'] = 1
            log.debug('Boto debug logging enabled')
        else:
            logging.getLogger('boto').setLevel(logging.INFO)
        if 'is_secure' not in kwargs:
            kwargs['is_secure'] = context.get('is_secure',
                                              cloud_config.get('is_secure',
                                                               True))
        self._connection = connect_to_region(region, **kwargs)
        log.info('Aminating in region {0}'.format(region))

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

    @retry(VolumeException, tries=2, delay=1, backoff=2, logger=log)
    def attach_volume(self, blockdevice, tag=True):

        context = self._config.context
        if "volume_id" in context.ami:
            volumes = self._connection.get_all_volumes(volume_ids=[context.ami.volume_id])
            if not volumes:
                raise VolumeException('Failed to find volume: {0}'.format(context.ami.volume_id))
            self._volume = volumes[0]
            return

        self.allocate_base_volume(tag=tag)
        # must do this as amazon still wants /dev/sd*
        ec2_device_name = blockdevice.replace('xvd', 'sd')
        log.debug('Attaching volume {0} to {1}:{2}({3})'.format(self._volume.id, self._instance.id, ec2_device_name,
                                                                blockdevice))
        self._volume.attach(self._instance.id, ec2_device_name)
        if not self.is_volume_attached(blockdevice):
            log.debug('{0} attachment to {1}:{2}({3}) timed out'.format(self._volume.id, self._instance.id,
                                                                        ec2_device_name, blockdevice))
            self._volume.add_tag('status', 'used')
            # trigger a retry
            raise VolumeException('Timed out waiting for {0} to attach to {1}:{2}'.format(self._volume.id,
                                                                                          self._instance.id,
                                                                                          blockdevice))
        log.debug('Volume {0} attached to {1}:{2}'.format(self._volume.id, self._instance.id, blockdevice))

    def is_volume_attached(self, blockdevice):
        context = self._config.context
        if "volume_id" in context.ami: return True

        try:
            self._volume_attached(blockdevice)
        except VolumeException:
            log.debug('Timed out waiting for volume {0} to attach to {1}:{2}'.format(self._volume.id,
                                                                                     self._instance.id, blockdevice))
            return False
        return True

    @retry(VolumeException, tries=10, delay=1, backoff=2, logger=log)
    def _volume_attached(self, blockdevice):
        status = self._volume.update()
        if status != 'in-use':
            raise VolumeException('Volume {0} not yet attached to {1}:{2}'.format(self._volume.id,
                                                                                  self._instance.id, blockdevice))
        elif not os_node_exists(blockdevice):
            raise VolumeException('{0} does not exist yet.'.format(blockdevice))
        else:
            return True

    def snapshot_volume(self, description=None):
        context = self._config.context
        if not description:
            description = context.snapshot.get('description', '')
        log.debug('Creating snapshot with description {0}'.format(description))
        self._snapshot = self._volume.create_snapshot(description)
        if not self._snapshot_complete():
            log.critical('Failed to create snapshot')
            return False
        else:
            log.debug('Snapshot complete. id: {0}'.format(self._snapshot.id))
            return True

    def _state_check(self, obj, state):
        obj.update()
        classname = obj.__class__.__name__
        if classname in ('Snapshot', 'Volume'):
            if classname == 'Snapshot':
                log.debug("Snapshot {0} state: {1}, progress: {2}".format(obj.id, obj.status, obj.progress))
            return obj.status == state
        else:
            return obj.state == state

    @retry(VolumeException, tries=600, delay=0.5, backoff=1.5, logger=log, maxdelay=10)
    def _wait_for_state(self, resource, state):
        if self._state_check(resource, state):
            log.debug('{0} reached state {1}'.format(resource.__class__.__name__, state))
            return True
        else:
            raise VolumeException('Timed out waiting for {0} to get to {1}({2})'.format(resource.id,
                                                                                     state,
                                                                                     resource.status))
    @lapse("aminator.cloud.ec2.ami_available.duration")
    def _ami_available(self):
        return self._wait_for_state(self._ami, 'available')

    @lapse("aminator.cloud.ec2.snapshot_completed.duration")
    def _snapshot_complete(self):
        return self._wait_for_state(self._snapshot, 'completed')

    @lapse("aminator.cloud.ec2.volume_available.duration")
    def _volume_available(self):
        return self._wait_for_state(self._volume, 'available')

    def detach_volume(self, blockdevice):
        context = self._config.context
        if "volume_id" in context.ami: return

        log.debug('Detaching volume {0} from {1}'.format(self._volume.id, self._instance.id))
        self._volume.detach()
        if not self._volume_detached(blockdevice):
            raise VolumeException('Time out waiting for {0} to detach from {1]'.format(self._volume.id,
                                                                                       self._instance.id))
        log.debug('Successfully detached volume {0} from {1}'.format(self._volume.id, self._instance.id))

    @retry(VolumeException, tries=7, delay=1, backoff=2, logger=log)
    def _volume_detached(self, blockdevice):
        status = self._volume.update()
        if status != 'available':
            raise VolumeException('Volume {0} not yet detached from {1}'.format(self._volume.id, self._instance.id))
        elif os_node_exists(blockdevice):
            raise VolumeException('Device node {0} still exists'.format(blockdevice))
        else:
            return True

    def delete_volume(self):
        context = self._config.context
        if "volume_id" in context.ami: return True

        log.debug('Deleting volume {0}'.format(self._volume.id))
        self._volume.delete()
        return self._volume_deleted()

    def _volume_deleted(self):
        try:
            self._volume.update()
        except EC2ResponseError, e:
            if e.code == 'InvalidVolume.NotFound':
                log.debug('Volume {0} successfully deleted'.format(self._volume.id))
                return True
            return False

    def is_stale_attachment(self, dev, prefix):
        log.debug('Checking for stale attachment. dev: {0}, prefix: {1}'.format(dev, prefix))
        if dev in self.attached_block_devices(prefix) and not os_node_exists(dev):
            log.debug('{0} is stale, rejecting'.format(dev))
            return True
        log.debug('{0} not stale, using'.format(dev))
        return False

    def save_registered_ami_id(self,ami_id):
        environ['AMINATOR_REGISTERED_AMI_ID'] = str(ami_id)

    def get_registered_ami_id(self):
        if 'AMINATOR_REGISTERED_AMI_ID' in environ:
            return environ['AMINATOR_REGISTERED_AMI_ID']
        return None

    @registration_retry(tries=3, delay=1, backoff=1)
    def _register_image(self, **ami_metadata):
        context = self._config.context
        ami = Image(connection=self._connection)
        ami.id = self._connection.register_image(**ami_metadata)
        if ami.id is None:
            return False
        else:
            while True:
                # spin until Amazon recognizes the AMI ID it told us about
                try:
                    sleep(2)
                    ami.update()
                    break
                except EC2ResponseError, e:
                    if e.error_code == 'InvalidAMIID.NotFound':
                        log.debug('{0} not found, retrying'.format(ami.id))
                    else:
                        raise e
            log.info('AMI registered: {0} {1}'.format(ami.id, ami.name))
            self.save_registered_ami_id(ami.id)
            context.ami.image = self._ami = ami
            return True

    def register_image(self, *args, **kwargs):
        context = self._config.context
        vm_type = context.ami.get("vm_type", "paravirtual")
        if 'manifest' in kwargs:
            ami_metadata = {
                'name': context.ami.name,
                'description': context.ami.description,
                'image_location': kwargs['manifest'],
                'virtualization_type': vm_type
            }
        else:
            # args will be [block_device_map, root_block_device]
            block_device_map, root_block_device = args[:2]
            bdm = self._make_block_device_map(block_device_map, root_block_device)
            ami_metadata = {
                'name': context.ami.name,
                'description': context.ami.description,
                'block_device_map': bdm,
                'root_device_name': root_block_device,
                'kernel_id': context.base_ami.kernel_id,
                'ramdisk_id': context.base_ami.ramdisk_id,
                'architecture': context.base_ami.architecture,
                'virtualization_type': vm_type
            }
            if vm_type == "hvm":
                del ami_metadata['kernel_id']
                del ami_metadata['ramdisk_id']

        if not self._register_image(**ami_metadata):
            return False
        return True

    def _make_block_device_map(self, block_device_map, root_block_device):
        bdm = BlockDeviceMapping(connection=self._connection)
        bdm[root_block_device] = BlockDeviceType(snapshot_id=self._snapshot.id,
                                                 delete_on_termination=True)
        for (os_dev, ec2_dev) in block_device_map:
            bdm[os_dev] = BlockDeviceType(ephemeral_name=ec2_dev)
        return bdm

    @retry(FinalizerException, tries=3, delay=1, backoff=2, logger=log)
    def add_tags(self, resource_type):
        context = self._config.context

        log.debug('Adding tags for resource type {0}'.format(resource_type))

        tags = context[resource_type].get('tags', None)
        if not tags:
            log.critical('Unable to locate tags for {0}'.format(resource_type))
            return False

        instance_var = '_' + resource_type
        try:
            instance = getattr(self, instance_var)
        except Exception:
            log.exception('Unable to find local instance var {0}'.format(instance_var))
            log.critical('Tagging failed')
            return False
        else:
            try:
                self._connection.create_tags([instance.id], tags)
            except EC2ResponseError:
                log.exception('Error creating tags for resource type {0}, id {1}'.format(resource_type, instance.id))
                raise FinalizerException('Error creating tags for resource type {0}, id {1}'.format(resource_type,
                                                                                                    instance.id))
            else:
                log.debug('Successfully tagged {0}({1})'.format(resource_type, instance.id))
                instance.update()
                tagstring = '\n'.join('='.join((key, val)) for (key, val) in tags.iteritems())
                log.debug('Tags: \n{0}'.format(tagstring))
                return True

    def attached_block_devices(self, prefix):
        log.debug('Checking for currently attached block devices. prefix: {0}'.format(prefix))
        self._instance.update()
        if device_prefix(self._instance.block_device_mapping.keys()[0]) != prefix:
            return dict((native_block_device(dev, prefix), mapping)
                        for (dev, mapping) in self._instance.block_device_mapping.iteritems())
        return self._instance.block_device_mapping

    def _resolve_baseami(self):
        log.info('Resolving base AMI')
        context = self._config.context
        cloud_config = self._config.plugins[self.full_name]
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
        self._resolve_baseami()
        self._instance = Instance(connection=self._connection)
        self._instance.id = get_instance_metadata()['instance-id']
        self._instance.update()

        
        context = self._config.context
        if context.ami.get("base_ami_name",None):
            environ["AMINATOR_BASE_AMI_NAME"] = context.ami.base_ami_name
        if context.ami.get("base_ami_id",None):
            environ["AMINATOR_BASE_AMI_ID"] = context.ami.base_ami_id

        if context.cloud.get("region", None):
            environ["AMINATOR_REGION"] = context.cloud.region

        return self
