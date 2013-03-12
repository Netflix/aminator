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
aminator.clouds.ec2.utils
=========================
wrappers for common ec2 operations
"""

import logging
import os
try:
    from collections import OrderedDict
except ImportError:
    from ordereddict import OrderedDict

import boto
from boto.ec2.blockdevicemapping import BlockDeviceMapping, BlockDeviceType

from aminator.clouds.ec2.data import ec2_obj_states
from aminator.clouds.ec2.core import ec2connection
from aminator.clouds.ec2.instanceinfo import this_instance
from aminator.utils import retry, os_node_exists, device_prefix
from aminator.config import config

log = logging.getLogger(__name__)

block_devices = OrderedDict()
for dev in config.ephemeral_devices:
    block_devices[os.path.basename(dev)] = dev

ROOT_BLOCK_DEVICE = config.root_device
EC2_DEVICE_PREFIX = 'sd'


# TODO: make this configurable?
def default_block_device_map(device_type='ephemeral'):
    """
    :param: device_type: ephemeral or ebs default block devices
    :rtype: `boto.ec2.blockdevicemapping.BlockDeviceMapping`
    :return: a ephemeral block device mapping for image registration
    """
    bdm = BlockDeviceMapping(connection=ec2connection())
    if device_type == 'ephemeral':
        for index, key in enumerate(block_devices.keys()):
            ephemeral_name = 'ephemeral{}'.format(index)
            bdm[key] = BlockDeviceType(ephemeral_name=ephemeral_name)
    else:
        # TODO: implement ebs?
        pass
    return bdm


def state_check(inst=None, state=None):
    """
    :type inst: any?
    :param inst: instance of an object with an update() method.
    :type state: str
    :param state: object state
    :rtype: bool
    :return: True if object's state matches state
    """
    assert hasattr(inst, 'update'), "%s doesn't have an update method." % str(inst)
    inst_name = type(inst).__name__
    assert state in ec2_obj_states[inst_name], "%s is not a recognized state for %s object." % (state, inst_name)
    inst.update()
    if inst_name == 'Snapshot':
        return inst.status == state
    else:
        return inst.state == state


@retry(StandardError, tries=600, delay=2, backoff=1, logger=log)
def wait_for_state(resource, state):
    if state_check(resource, state):
        return True
    raise StandardError('waiting for {} to get to {}({})'.format(resource.id, state, resource.status))


def ami_available(ami):
    return wait_for_state(ami, 'available')


def snapshot_complete(snapshot):
    return wait_for_state(snapshot, 'completed')


def register(**reg_args):
    """
    register an EC2 image. See boto.ec2.connection.EC2Connection.register_image() for param details.
    Re-register with a revised name on name collisions.
    :rtype: :class:`boto.ec2.image.Image`
    :return: The registered Image or None on failure
    """
    ec2 = ec2connection()
    try:
        name = reg_args['name']
    except KeyError:
        log.error('register called without a name parameter')
        return None

    retries = 0
    ami = boto.ec2.image.Image(connection=ec2)
    while True:
        try:
            ami.id = ec2.register_image(**reg_args)
            break
        except boto.exception.EC2ResponseError as e:
            if e.error_code == 'InvalidAMIName.Duplicate' and retries < 2:
                retries += 1
                reg_args['name'] = name + (".r%0d" % retries)
                log.debug("Duplicate Name: re-registering with %s" % reg_args['name'])
            else:
                for (code, msg) in e.errors:
                    log.debug("EC2ResponseError: %s: %s." % (code, msg))
                return None
    log.debug('%s registered' % ami.id)
    if ami_available(ami):
        return ami
    else:
        return None


@retry(StandardError, tries=3, delay=1, backoff=2, logger=log)
def add_tags(resource_ids, tags):
    """
    :type resource_ids: list
    :param resource_ids: list containing the EC2 resource IDs to apply tags to
    :type tags: dict
    :param tags: dictionary of tag name/values to be applied to resource_ids
    :rtype bool: returns True if the operation succeeds
    """
    ec2 = ec2connection()
    try:
        ec2.create_tags(resource_ids, tags)
        return True
    except boto.exception.EC2ResponseError as e:
        log.debug(e)
        raise(StandardError('create_tags failure.'))
    return False


def stale_attachment(dev):
    """
    :type dev: str
    :param dev: device node to check
    :rtype: bool
    :return: True device appears stale. That is, if AWS thinks a volume is attached to dev
             but the OS does see the device node.
    """
    block_devs = this_instance.block_devs
    if dev in block_devs and not os_node_exists(dev):
        return True
    return False


def ec2_block_device(source_device):
    """translate source_device to be of a form acceptable by EC2 API.
    That is, /dev/sd..."""
    source_device_prefix = device_prefix(source_device)
    if source_device_prefix != EC2_DEVICE_PREFIX:
        # ec2 API only accepts 'sd' device names.
        return source_device.replace(source_device_prefix, EC2_DEVICE_PREFIX)
    else:
        return source_device
