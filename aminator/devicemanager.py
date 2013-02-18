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

from aminator.clouds.ec2.utils import stale_attachment
from aminator.utils import Flock, locked


log = logging.getLogger(__name__)
# TODO: make configurable
lockdir = '/var/lock'
dev_alloc_lock = os.path.join(lockdir, 'dev_alloc')

# make these configurables
ALLOWED_MAJORS = 'fghijklmnop'
DEVICE_FORMAT = '/dev/sd{0}{1}'

minor_devs = [DEVICE_FORMAT.format(major, minor) for major in 'fghijklmnop' for minor in xrange(1, 16)]


class DeviceManager(object):
    """Provides device allocation. Intened to be used in a context manager, makes best effort to identify
    an unused device node by serializing through '/var/lock/dev_alloc'
    with DeviceManager as dev:
        vol.attach(dev.node)
    """
    def __init__(self):
        self.node = None
        self.fh = None

    def __enter__(self):
        with Flock(dev_alloc_lock):
            self._get_dev()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        fcntl.flock(self.fh, fcntl.LOCK_UN)
        self.fh.close()

    def _get_dev(self):
        for dev in minor_devs:
            device_node_lock = os.path.join(lockdir, os.path.basename(dev))
            if os.path.exists(dev):
                log.debug('%s exists' % dev)
                continue
            elif locked(device_node_lock):
                log.debug('%s is locked' % dev)
                continue
            elif stale_attachment(dev):
                log.debug('%s is stale' % dev)
                continue
            else:
                self.node = dev
                self.fh = open(device_node_lock, 'a')
                fcntl.flock(self.fh, fcntl.LOCK_EX)
                log.debug('fh = %s, dev = %s' % (str(self.fh), self.node))
                break
