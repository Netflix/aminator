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
from contextlib import contextmanager
from time import sleep

import envoy

from aminator.config import config


log = logging.getLogger(__name__)


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
    dir += ' '
    pattern = re.compile(dir)
    with open('/proc/mounts') as mounts:
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
    for prefix in config.device_prefixes:
        if any(device.startswith(prefix) for device in os.listdir('/sys/block')):
            return prefix
    else:
        return None


def device_prefix(source_device):
    # strip off any incoming /dev/ foo
    source_device_name = os.path.basename(source_device)
    # if we have a subdevice/partition...
    if source_device_name[-1].isdigit():
        # then its prefix is the name minus the last TWO chars
        return source_device_name[:-2:]
    else:
        # otherwise, just strip the last one
        return source_device_name[:-1:]


def native_block_device(source_device):
    native_prefix = native_device_prefix()
    source_device_prefix = device_prefix(source_device)
    if source_device_prefix == native_prefix:
        # we're okay, using the right name already, just return the same name
        return source_device
    else:
        # sub out the bad prefix for the good
        return source_device.replace(source_device_prefix, native_prefix)


def shlog(command):
    log.debug(command)
    ret = envoy.run(command)
    for x in (ret.std_err + ret.std_out).splitlines():
        log.debug(x)
    return(ret.status_code == 0)


def fsck(dev):
    return shlog("fsck -y {0}".format(dev))


def mount(dev, mountpoint, fstype='', options=''):
    """
    wrapper for mount
    :type dev: str
    :param dev: device node to mount
    :type mountpoint: str
    :param mountpoint: directory mount point
    :rtype: bool
    :return: True if mount succeeds.
    """
    fstype_flag = ''
    fstype_arg = ''
    if fstype:
        if fstype == 'bind':
            fstype_flag = '-o'
        else:
            fstype_flag = '-t'
        fstype_arg = '{0} {1}'.format(fstype_flag, fstype)
    options_arg = options
    if options:
        options_arg = '-o ' + options
    mount_cmd = 'mount {0} {1} {2} {3}'.format(fstype_arg, options_arg, dev, mountpoint)
    return shlog(mount_cmd)


def unmount(dev):
    """shell command wrapper for unmounting device
    :type dev: str
    :param dev: device node to mount
    :rtype: bool
    :return: True if unmount succeeds.
    """
    return shlog("umount {0}".format(dev))


def busy_mount(mnt):
    return shlog('lsof -X {0}'.format(mnt))


@contextmanager
def os_closing(fd):
    """
    Intended to wrap os.open() and close the descriptor when done

    :param fd: file descriptor from os.open
    """
    try:
        yield fd
    finally:
        os.close(fd)


@contextmanager
def chroot(path):
    """
    Perform some actions from a chroot environment

    :param path: The new root
    :type path: str
    """
    if not path or not os.path.isdir(path):
        raise IOError('chroot: path not provided or not found: {0}'.format(path))

    if os.geteuid != 0:
        raise OSError(13, 'Must be root')

    with os_closing(os.open('/', os.O_RDONLY)) as real_root:
        cwd = os.getcwd()
        log.debug('cwd: {0}'.debug(cwd))
        os.chroot(path)
        os.chdir('/')
        yield
        os.fchdir(real_root)
        os.chroot('.')
        os.chdir(cwd)


def chroot_setup(root, rootdev):
    """
    Takes mounts specified in configuration and lays them
    on top of the chroot environment
    :param root: chroot root path
    :param rootdev: chroot root device
    :return: True on successful setup, False if errors
    """
    if not mounted(root):
        if not mount(rootdev, root):
            log.error('Unable to mount chroot device {0} at {1}'.format(rootdev, root))
            return False

    for device, fstype, mountpoint in config.chroot_mounts:
        chroot_mountpoint = os.path.join(root, mountpoint.lstrip('/'))
        if not os.path.exists(chroot_mountpoint):
            log.error('{0} does not exist'.format(chroot_mountpoint))
            return False
        if not mounted(chroot_mountpoint):
            if not mount(device, chroot_mountpoint, fstype):
                log.error('Unable to mount {0} on {1} fstype {2}'.format(device, chroot_mountpoint,
                                                                         fstype))
                return False
        return True


def chroot_teardown(root):
    """
    Unmounts a chroot environment
    :param root: chroot root path
    :return: True if everything unmounts okay, False if errors
    """
    if busy_mount(root):
        log.error('Unable to teardown {}, device busy'.format(root))
        return False
    if not mounted(root):
        return True
    # unmount in reverse order to account for layered mounts
    for device, fstype, mountpoint in reversed(config.chroot_mounts):
        chroot_mountpoint = os.path.join(root, mountpoint.lstrip('/'))
        if not mounted(chroot_mountpoint):
            continue
        if not unmount(chroot_mountpoint):
            log.error('Unable to unmount {0}'.format(chroot_mountpoint))
            return False
    for mountpoint in lifo_mounts(root):
        if not unmount(mountpoint):
            log.error('Unable to unmount {0}'.format(mountpoint))
            return False
    return unmount(root)


def lifo_mounts(root):
    """return list of mount points mounted on 'root'
    and below in lifo order from /proc/mounts."""
    with open('/proc/mounts') as proc_mounts:
        # grab the mountpoint for each mount where we MIGHT match
        mount_entries = [line.split(' ')[1] for line in proc_mounts if root in line]
    if not mount_entries:
        # return an empty list if we didn't match
        return mount_entries
    return [entry for entry in reversed(mount_entries)
            if entry == root or entry.startswith(root+'/')]


# Retry decorator with backoff
# http://wiki.python.org/moin/PythonDecoratorLibrary#Retry
def retry(ExceptionToCheck, tries=3, delay=0.5, backoff=1, logger=None):
    """
    Retries a function or method until it returns True.

    delay sets the initial delay in seconds, and backoff sets the factor by which
    the delay should lengthen after each failure. backoff must be greater than 1,
    or else it isn't really a backoff. tries must be at least 0, and delay
    greater than 0.
    """
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


@contextmanager
def flock(filename):
    """simple blocking exclusive file locker
       eg:
       with flock(lockfilepath):
           ...
    """
    with open(filename, 'a') as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        yield
        fcntl.flock(fh, fcntl.LOCK_UN)


def locked(filename):
    """
    :param filename:
    :return: True if file is locked.
    """
    with open(filename, 'a') as fh:
        try:
            fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
            ret = False
        except IOError as e:
            log.debug('{0} is locked: {1}'.format(filename, e))
            ret = True
    return ret
