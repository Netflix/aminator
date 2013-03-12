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

import fcntl
import logging
import os
from contextlib import contextmanager

from aminator.clouds.ec2.utils import stale_attachment
from aminator.exceptions import DeviceError
from aminator.utils import flock, locked, native_device_prefix
from aminator.config import config


log = logging.getLogger(__name__)


def allowed_devices():
    """
    Returns a sequence consisting of allowed device names for attaching volumes
    """
    majors = config.nonpartitioned_device_letters
    device_prefix = native_device_prefix()
    device_format = '/dev/{0}{1}{2}'

    return [device_format.format(device_prefix, major, minor) for major in majors
            for minor in xrange(1, 16)]


def find_available_dev():
    """
    Iterates through allowed devices and attempts to return a free device
    To be safe, wrap this call in a flock so only one process can hunt at a
    time. Better, use the @device() context manager!

    :returns: tuple(device node, device handle)
    """
    for dev in allowed_devices():
        device_node_lock = os.path.join(config.lockdir, os.path.basename(dev))
        if os.path.exists(dev):
            log.debug('%s exists, skipping' % dev)
            continue
        if locked(device_node_lock):
            log.debug('%s is locked, skipping' % dev)
            continue
        if stale_attachment(dev):
            log.debug('%s is stale, skipping' % dev)
            continue
        fh = open(device_node_lock, 'a')
        fcntl.flock(fh, fcntl.LOCK_EX)
        log.debug('fh = {0}, dev = {1}'.format(str(fh), dev))
        return (dev, fh)
    else:
        raise DeviceError('Exhausted all devices, none free')


@contextmanager
def device():
    """
    Provides device allocation. If used in a context manager, makes best effort to identify
    an unused device node by serializing through '{lockdir}/dev_alloc' and '{lockdir}/dev'

    with device as dev:
        vol.attach(dev)
    """
    dev_alloc_lock = os.path.join(config.lockdir, 'dev_alloc')
    with flock(dev_alloc_lock):
        dev, dev_lock_handle = find_available_dev()
    yield dev
    fcntl.flock(dev_lock_handle, fcntl.LOCK_UN)
    dev_lock_handle.close()
