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
import functools
import logging
import os
import re
import stat
import envoy
from time import sleep


log = logging.getLogger(__name__)
pid = os.getpid()
# TODO: make configurable?
BIND_DIRS = ('/dev', '/proc', '/sys')
DEVICE_PREFIXES = ('sd', 'xvd')


def mounted(dir=None):
    """
    :type dir: str
    :param dir: device or mount point to look for in /proc/mounts

    :rtype: bool
    :return: True if dir is found in /proc/mounts.
    """
    if dir is None:
        return False
    # strip trailing white space then add a single space
    # anchor to differentiate from, say, sdf1 and sdf11
    dir = dir.rstrip()
    dir += " "
    pattern = re.compile(dir)
    with open("/proc/mounts") as mounts:
        return any(pattern.search(mount) for mount in mounts)


def os_node_exists(dev=None):
    """
    :type dev: str
    :param dev: path to device node, eg. /dev/sdf1
    :rtype: bool
    :return: True if dev is a device node
    """
    if dev is None:
        return False
    try:
        mode = os.stat(dev).st_mode
    except OSError:
        return False
    return stat.S_ISBLK(mode)


def native_device_prefix():
    for prefix in DEVICE_PREFIXES:
        if any(device.startswith(prefix) for device in os.listdir('/sys/block')):
            return prefix
    else:
        return None


def sudo():
    sudo = ''
    if os.geteuid() > 0:
        sudo = 'sudo '
    return sudo


def shlog(command):
    log.debug(command)
    ret = envoy.run(command)
    for x in (ret.std_err + ret.std_out).splitlines():
        log.debug(x)
    return(ret.status_code == 0)


def fsck(dev):
    return shlog(sudo() + "fsck -y {}".format(dev))


def mount(dev, mnt, opts=""):
    """shell command wrapper for mounting device to mount point
    :type dev: str
    :param dev: device node to mount
    :type mnt: str
    :param mnt: directory mount point
    :rtype: bool
    :return: True if mount succeeds.
    """
    return shlog(sudo() + "mount {} {} {}".format(opts, dev, mnt))


def unmount(dev):
    """shell command wrapper for unmounting device
    :type dev: str
    :param dev: device node to mount
    :rtype: bool
    :return: True if unmount succeeds.
    """
    return shlog(sudo() + "umount {}".format(dev))


def busy_mount(mnt):
    return shlog('lsof -X {}'.format(mnt))


def chroot_mount(dev, mnt):
    """mount dev on mnt with BIND_DIRS mounted to mnt/{bid_dirs}
    :type dev: str
    :param dev: device node to mount
    :rtype: bool
    :return: True if unmount succeeds.
    """
    if not mounted(mnt):
        if not mount(dev, mnt):
            return False
    for _dir in BIND_DIRS:
        bind_mnt = os.path.join(mnt, _dir.lstrip('/'))
        if not os.path.exists(bind_mnt):
            log.debug(bind_mnt + " does not exist.")
            return False
        if not mounted(bind_mnt):
            if not mount(_dir, bind_mnt, '--bind'):
                return False
    return True


def chroot_unmount(mnt):
    if busy_mount(mnt):
        return False
    for _dir in BIND_DIRS:
        bind_mnt = os.path.join(mnt, _dir.lstrip('/'))
        if not mounted(bind_mnt):
            continue
        if not unmount(bind_mnt):
            return False
    return unmount(mnt)


# Retry decorator with backoff
# http://wiki.python.org/moin/PythonDecoratorLibrary#Retry
def retry(ExceptionToCheck, tries=3, delay=0.5, backoff=1, logger=None):
    '''Retries a function or method until it returns True.

    delay sets the initial delay in seconds, and backoff sets the factor by which
    the delay should lengthen after each failure. backoff must be greater than 1,
    or else it isn't really a backoff. tries must be at least 0, and delay
    greater than 0.'''
    if logger is None:
        logger = log

    def deco_retry(f):
        def f_retry(*args, **kwargs):
            mtries, mdelay = tries, delay
            while mtries > 0:
                try:
                    return f(*args, **kwargs)
                except ExceptionToCheck, e:
                    logger.debug(e)
                    sleep(mdelay)
                    mtries -= 1
                    mdelay *= backoff
            return f(*args, **kwargs)
        return f_retry  # true decorator
    return deco_retry


# http://wiki.python.org/moin/PythonDecoratorLibrary#Alternate_memoize_as_nested_functions
def memoize(obj):
    cache = obj.cache = {}

    @functools.wraps(obj)
    def memoizer(*args, **kwargs):
        if args not in cache:
            cache[args] = obj(*args, **kwargs)
        return cache[args]
    return memoizer


def copy_image(src, dst):
    """dd like utility for copying image files.
       eg.
       copy_image('/dev/sdf1','/mnt/bundles/ami-name.img')
    """
    try:
        src_fd = os.open(src, os.O_RDONLY)
        dst_fd = os.open(dst, os.O_WRONLY | os.O_CREAT, 0644)
        blks = 0
        blksize = 64 * 1024
        log.debug("copying %s to %s" % (src, dst))
        while True:
            buf = os.read(src_fd, blksize)
            if len(buf) <= 0:
                log.debug("%d %d blocks written." % (blks, blksize))
                os.close(src_fd)
                os.close(dst_fd)
                break
            out = os.write(dst_fd, buf)
            if out < blksize:
                log.debug("wrote %d bytes." % (out))
            blks += 1
    except os.OSError as e:
        log.debug("%s: errno[%d]: %s." % (e.filename, e.errno, e.strerror))
        return False
    return True


class Flock(object):
    """simple blocking exclusive file locker
       eg:
       with Flock(lockfilepath):
           ...
    """
    def __init__(self, file=""):
        if not os.path.exists(os.path.dirname(file)):
            raise(Exception)
        self.fh = open(file, 'a')

    def __enter__(self):
        fcntl.flock(self.fh, fcntl.LOCK_EX)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        fcntl.flock(self.fh, fcntl.LOCK_UN)
        self.fh.close()


def locked(file=""):
    """
    :return: True if file is locked.
    """
    if not os.path.exists(os.path.dirname(file)):
        raise(Exception)
    fh = open(file, 'a')
    try:
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        ret = False
    except IOError as e:
        log.debug("%s is locked: %s" % (file, e))
        ret = True
    fh.close()
    return ret
