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

import boto
import boto.utils
from boto.regioninfo import RegionInfo

from aminator.utils import memoize


def ec2connection(region=None):
    """
    :type region: str
    :param region: region for which to set connection endpoint
    :rtype: :class:`boto.ec2.connection.EC2Connection`
    :return: A connection to Amazon's EC2 service with an endpoint of the local region
             None if not an ec2 instance.
    """
    if region is None and is_ec2_instance is False:
        region = 'us-east-1'
    elif region is None:
        region = boto.utils.get_instance_metadata()['placement']['availability-zone'][:-1]

    ec2regioninfo = RegionInfo(name=region, endpoint='ec2.%s.amazonaws.com' % (region))
    return boto.connect_ec2(region=ec2regioninfo, is_secure=True)


# TODO: I think we need a better check as the get_instance_metadata takes *ages* to timeout
@memoize
def is_ec2_instance():
    """
    :rtype: bool
    :return: True if the ec2 instance meta-data url is accessible, Return true, else False.
    """
    is_instance = boto.utils.get_instance_metadata(timeout=2)
    return is_instance is not None
