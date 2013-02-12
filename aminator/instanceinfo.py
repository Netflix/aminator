# encoding: utf-8
"""
Copyright (c) 2012 Netflix, Inc. All rights reserved.
"""

import logging
import boto
import boto.ec2
import boto.utils
from boto.regioninfo import RegionInfo

from aminator import NullHandler

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)
log.addHandler(NullHandler())

__is_ec2_instance = None


def _is_ec2_instance():
    """
    :rtype: bool
    :return: True if the ec2 instance meta-data url is accessible, Return true, else False.
    """
    global __is_ec2_instance
    if __is_ec2_instance is None:
        __is_ec2_instance = (boto.utils.get_instance_metadata(timeout=2) is not None)
    return __is_ec2_instance


def ec2connection(region=None):
    """
    :type region: str
    :param region: region for which to set connection endpoint
    :rtype: :class:`boto.ec2.connection.EC2Connection`
    :return: A connection to Amazon's EC2 service with an endpoint of the local region
             None if not an ec2 instance.
    """
    if region is None and _is_ec2_instance() is False:
        region = 'us-east-1'
    elif region is None:
        region = boto.utils.get_instance_metadata()['placement']['availability-zone'][:-1]

    ec2regioninfo = RegionInfo(name=region, endpoint='ec2.%s.amazonaws.com' % (region))
    return boto.connect_ec2(region=ec2regioninfo, is_secure=True)


class InstanceInfo(boto.ec2.instance.Instance):
    def __init__(self):
        self.id = None
        self.connection = ec2connection()
        if _is_ec2_instance():
            self.id = boto.utils.get_instance_metadata()['instance-id']
            self.update()

    def setReadOnly(self, value):
        raise AttributeError

    @property
    def is_instance(self):
        return self.id is not None

    @property
    def block_devs(self):
        if not self.is_instance:
            return None
        self.update()
        return self.block_device_mapping

    @property
    def az(self):
        if not self.is_instance:
            return None
        return self.placement

    @property
    def region(self):
        if not self.is_instance:
            return None
        return self.placement[:-1]

    @property
    def owner_id(self):
        if not self.is_instance:
            return None
        return boto.utils.get_instance_metadata(timeout=5)['network']['interfaces']['macs'].values()[0]['owner-id']

this_instance = InstanceInfo()
