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
aminator.util.linux
===================
Linux utility functions
"""

import errno
import fcntl
import logging
import os
import stat
from collections import namedtuple
from contextlib import contextmanager

import envoy
from decorator import decorator


log = logging.getLogger(__name__)
MountSpec = namedtuple('MountSpec', 'dev mountpoint fstype options')
CommandResult = namedtuple('CommandResult', 'success result')


def command(timeout=None, data=None, *cargs, **ckwargs):
    """
    decorator used to define shell commands to be executed via envoy.run
    decorated function should return a simple string representing the command to be executed
    decorated function should return None if a guard fails
    """
    @decorator
    def _run(f, *args, **kwargs):
        _cmd = f(*args, **kwargs)
        if _cmd is None:
            return CommandResult(False, None)
        log.debug('command: {0}'.format(_cmd))
        res = envoy.run(_cmd, timeout, data, *cargs, **ckwargs)
        log.debug('stdout:\n{0}'.format(res.std_out))
        log.debug('stderr:\n{0}'.format(res.std_err))
        return CommandResult(res.status_code == 0, res)
    return _run


def mounted(path):
    pat = path.strip() + ' '
    with open('/proc/mounts') as mounts:
        return any(pat in mount for mount in mounts)


def os_node_exists(dev):
    try:
        mode = os.stat(dev).st_mode
    except OSError:
        return False
    return stat.S_ISBLK(mode)

@command()
def fsck(dev):
    return 'fsck -y {0}'.format(dev)


@command()
def mount(mountspec):
    if not any((mountspec.dev, mountspec.mountpoint)):
        log.error('Must provide dev or mountpoint')
        return None

    fstype_arg = options_arg = ''

    if mountspec.fstype:
        if mountspec.fstype == 'bind':
            fstype_flag = '-o'
        else:
            fstype_flag = '-t'
        fstype_arg = '{0} {1}'.format(fstype_flag, mountspec.fstype)

    if mountspec.options:
        options_arg = '-o ' + mountspec.options

    return 'mount {0} {1} {2} {3}'.format(fstype_arg, options_arg, mountspec.dev, mountspec.mountpoint)


@command()
def unmount(dev):
    return 'unmount {0}'.format(dev)


@command()
def busy_mount(mountpoint):
    return 'lsof -X {0}'.format(mountpoint)


@contextmanager
def os_closing(fh):
    """
    Intended to wrap os.open() and close the descriptor when done
    """
    try:
        yield fh
    finally:
        os.close(fh)


@contextmanager
def chroot(path):
    """
    Perform some actions from a chroot environment

    :param path: The new root
    """
    if not path or not os.path.isdir(path):
        raise IOError('chroot: path not provided or not found: {0}'.format(path))

    with os_closing(os.open('/', os.O_RDONLY)) as real_root:
        cwd = os.getcwd()
        log.debug('cwd: {0}'.debug(cwd))
        os.chroot(path)
        os.chdir('/')
        yield
        os.fchdir(real_root)
        os.chroot('.')
        os.chdir(cwd)


def chroot_setup(root, mounts):
    """
    Takes a root path and overlays special mounts on top
    :param root: chroot root path
    :param mounts: iterable collection of MountSpec tuples
    :type mounts: list
    :return: True on successful setup, False if errors
    """
    for mountspec in mounts:
        rootpath = os.path.join(root, mountspec.mountpoint)
        if not os.path.exists(rootpath):
            log.error('{0} does not exist'.format(rootpath))
            return False
        if not mount(mountspec).success:
            log.error('Unable to mount {0} on {1} fstype {2}'.format(device, chroot_mountpoint,
                                                                     fstype))
            return False
        return True


def chroot_teardown(root, mounts):
    """
    Unmounts a chroot environment
    :param root: chroot root path
    :param mounts: tuple of tuples of dev,fstype,mountpoint
    :return: True if everything unmounts okay, False if errors
    """
    if busy_mount(root):
        log.error('Unable to teardown {}, device busy'.format(root))
        return False
    if not mounted(root):
        return True
    # unmount in reverse order to account for layered mounts
    for device, fstype, mountpoint in reversed(mounts):
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
    return unmount(root).success


def lifo_mounts(root=None):
    """return list of mount points mounted on 'root'
    and below in lifo order from /proc/mounts."""
    with open('/proc/mounts') as proc_mounts:
        # grab the mountpoint for each mount where we MIGHT match
        mount_entries = [line.split(' ')[1] for line in proc_mounts if root in line]
    if not mount_entries:
        # return an empty list if we didn't match
        return mount_entries
    return [entry for entry in reversed(mount_entries)
            if entry == root or entry.startswith(root + '/')]


def copy_image(src=None, dst=None):
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
                log.debug('wrote {0} bytes.'.format(out))
            blks += 1
    except OSError as e:
        log.debug("%s: errno[%d]: %s." % (e.filename, e.errno, e.strerror))
        return False
    return True


@contextmanager
def flock(filename=None):
    """simple blocking exclusive file locker
       eg:
       with flock(lockfilepath):
           ...
    """
    with open(filename, 'a') as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        yield
        fcntl.flock(fh, fcntl.LOCK_UN)


def locked(filename=None):
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


def root_check():
    """
    Simple root gate
    :return: errno.EACCESS if not running as root, None if running as root
    """
    if os.geteuid() != 0:
        return errno.EACCESS
    return None
