# encoding: utf-8
"""
shortcuts and helpers for boto scripts

Created by mtripoli on 2012-07-06.
Copyright (c) 2012 Netflix, Inc. All rights reserved.
"""

import os
import fcntl
import re
import stat
from time import sleep
import logging
import boto
import boto.ec2
import boto.utils

from aminator import NullHandler
from aminator.ec2_data import ec2_obj_states
from aminator.instanceinfo import this_instance, ec2connection

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)
log.addHandler(NullHandler())

pid = str(os.getpid())


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


def mount(dev, mnt):
    """shell command wrapper for mounting device to mount point
    :type dev: str
    :param dev: device node to mount
    :type mnt: str
    :param mnt: directory mount point
    :rtype: bool
    :return: True if mount succeeds.
    """
    cmd = boto.utils.ShellCommand("/usr/bin/aminator.sh -t %s -a mount %s %s" % (pid, dev, mnt))
    if cmd.getStatus() != 0:
        log.debug(cmd.output)
        return False
    return True


def unmount(dev):
    """shell command wrapper for unmounting device
    :type dev: str
    :param dev: device node to mount
    :rtype: bool
    :return: True if unmount succeeds.
    """
    cmd = boto.utils.ShellCommand("/usr/bin/aminator.sh -t %s -a unmount %s" % (pid, dev))
    if cmd.getStatus() != 0:
        log.debug(cmd.output)
        return False
    return True


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
