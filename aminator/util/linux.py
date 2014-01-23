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
import shutil
import stat
import string
from collections import namedtuple
from contextlib import contextmanager

import envoy
from decorator import decorator


log = logging.getLogger(__name__)
MountSpec = namedtuple('MountSpec', 'dev fstype mountpoint options')
CommandResult = namedtuple('CommandResult', 'success result')
# need to scrub anything not in this list from AMI names and other metadata
SAFE_AMI_CHARACTERS = string.ascii_letters + string.digits + '().-/_'


def command(timeout=None, data=None, *cargs, **ckwargs):
    """
    decorator used to define shell commands to be executed via envoy.run
    decorated function should return a list or string representing the command to be executed
    decorated function should return None if a guard fails
    """
    @decorator
    def _run(f, *args, **kwargs):
        _cmd = f(*args, **kwargs)
        assert _cmd is not None, "null command passed to @command decorator"
        if isinstance(_cmd, list):
            log.debug('command: {0}'.format(" ".join(_cmd)))
            _cmd = [_cmd]
        else:
            log.debug('command: {0}'.format(_cmd))
        res = envoy.run(_cmd, timeout, data, *cargs, **ckwargs)
        if any((res.std_out, res.std_err)):
            log.debug('stdout: {0.std_out}\nstderr: {0.std_err}'.format(res))
        log.debug('status code: {0}'.format(res.status_code))
        return CommandResult(res.status_code == 0, res)
    return _run


def mounted(path):
    pat = path.strip() + ' '
    with open('/proc/mounts') as mounts:
        return any(pat in mount for mount in mounts)


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
    return 'umount {0}'.format(dev)


@command()
def busy_mount(mountpoint):
    return 'lsof -X {0}'.format(mountpoint)


def sanitize_metadata(word):
    chars = list(word)
    for index, char in enumerate(chars):
        if char not in SAFE_AMI_CHARACTERS:
            chars[index] = '_'
    return ''.join(chars)


def keyval_parse(record_sep='\n', field_sep=':'):
    """decorator for parsing CommandResult stdout into key/value pairs returned in a dict
    """
    @decorator
    def _parse(f, *args, **kwargs):
        metadata = {}
        ret = f(*args, **kwargs)
        if ret.success:
            for record in ret.result.std_out.split(record_sep):
                try:
                    key, val = record.split(field_sep, 1)
                except ValueError:
                    continue
                metadata[key.strip()] = val.strip()
        else:
            log.debug('failure:{0.command} :{0.std_err}'.format(ret.result))
        return metadata
    return _parse


class Chroot(object):
    def __init__(self, path):
        self.path = path
        log.debug('Chroot path: {0}'.format(self.path))

    def __enter__(self):
        log.debug('Configuring chroot at {0}'.format(self.path))
        self.real_root = os.open('/', os.O_RDONLY)
        self.cwd = os.getcwd()
        os.chroot(self.path)
        os.chdir('/')
        log.debug('Inside chroot')
        return self

    def __exit__(self, typ, exc, trc):
        if typ: log.exception("Exception: {0}: {1}".format(typ.__name__,exc))
        log.debug('Leaving chroot')
        os.fchdir(self.real_root)
        os.chroot('.')
        os.chdir(self.cwd)
        log.debug('Outside chroot')
        return False


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
        log.debug("copying {} to {}".format(src,dst))
        while True:
            buf = os.read(src_fd, blksize)
            if len(buf) <= 0:
                log.debug("{} {} blocks written.".format(blks,blksize))
                os.close(src_fd)
                os.close(dst_fd)
                break
            out = os.write(dst_fd, buf)
            if out < blksize:
                log.debug('wrote {0} bytes.'.format(out))
            blks += 1
    except OSError as e:
        log.debug("{}: errno[{}]: {}.".format(e.filename, e.errno, e.strerror))
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
        return errno.EACCES
    return None


def native_device_prefix(prefixes):
    log.debug('Getting the OS-native device prefix from potential prefixes: {0}'.format(prefixes))
    for prefix in prefixes:
        if any(device.startswith(prefix) for device in os.listdir('/sys/block')):
            log.debug('Native prefix is {0}'.format(prefix))
            return prefix
    log.debug('{0} contains no native device prefixes'.format(prefixes))
    return None


def device_prefix(source_device):
    log.debug('Getting prefix for device {0}'.format(source_device))
    # strip off any incoming /dev/ foo
    source_device_name = os.path.basename(source_device)
    # if we have a subdevice/partition...
    if source_device_name[-1].isdigit():
        # then its prefix is the name minus the last TWO chars
        log.debug('Device prefix for {0} is {1}'.format(source_device, source_device_name[:-2:]))
        return source_device_name[:-2:]
    else:
        # otherwise, just strip the last one
        log.debug('Device prefix for {0} is {1}'.format(source_device, source_device_name[:-1:]))
        return source_device_name[:-1:]


def native_block_device(source_device, native_prefix):
    source_device_prefix = device_prefix(source_device)
    if source_device_prefix == native_prefix:
        # we're okay, using the right name already, just return the same name
        return source_device
    else:
        # sub out the bad prefix for the good
        return source_device.replace(source_device_prefix, native_prefix)


def os_node_exists(dev):
    try:
        mode = os.stat(dev).st_mode
    except OSError:
        return False
    return stat.S_ISBLK(mode)


def install_provision_config(src, dstpath, backup_ext='_aminator'):
    if os.path.isfile(src) or os.path.isdir(src):
        log.debug('Copying {0} from the aminator host to {1}'.format(src, dstpath))
        dst = os.path.join(dstpath.rstrip('/'), src.lstrip('/'))
        log.debug('copying src: {0} dst: {1}'.format(src, dst))
        try:
            if os.path.isfile(dst) or os.path.islink(dst) or os.path.isdir(dst):
                backup = '{0}{1}'.format(dst, backup_ext)
                log.debug('Moving existing {0} out of the way'.format(dst))
                try:
                    os.rename(dst, backup)
                except Exception:
                    log.exception('Error encountered while copying {0} to {1}'.format(dst, backup))
                    return False
            if os.path.isdir(src):
                shutil.copytree(src,dst,symlinks=True)
            else:
                shutil.copy(src,dst)
        except Exception:
            log.exception('Error encountered while copying {0} to {1}'.format(src, dst))
            return False
        log.debug('{0} copied from aminator host to {1}'.format(src, dstpath))
        return True
    else:
        log.critical('File not found: {0}'.format(src))
        return True


def install_provision_configs(files, dstpath, backup_ext='_aminator'):
    for filename in files:
        if not install_provision_config(filename, dstpath, backup_ext):
            return False
    return True


def remove_provision_config(src, dstpath, backup_ext='_aminator'):
    dst = os.path.join(dstpath.rstrip('/'), src.lstrip('/'))
    backup = '{0}{1}'.format(dst, backup_ext)
    try:
        if os.path.isfile(dst) or os.path.islink(dst) or os.path.isdir(dst):
            log.debug('Removing {0}'.format(dst))
            try:
                if os.path.isdir(dst):
                    shutil.rmtree(dst)
                else:
                    os.remove(dst)
                log.debug('Provision config {0} removed'.format(dst))
            except Exception:
                log.exception('Error encountered while removing {0}'.format(dst))
                return False

        if os.path.isfile(backup) or os.path.islink(backup) or os.path.isdir(backup):
            log.debug('Restoring {0} to {1}'.format(backup, dst))
            os.rename(backup, dst)
            log.debug('Restoration of {0} to {1} successful'.format(backup, dst))
        else:
            log.warn('No backup file {0} was found'.format(backup))
    except Exception:
        log.exception('Error encountered while restoring {0} to {1}'.format(backup, dst))
        return False
    return True


def remove_provision_configs(sources, dstpath, backup_ext='_aminator'):
    for filename in sources:
        if not remove_provision_config(filename, dstpath, backup_ext):
            return False
    return True


def short_circuit(root, cmd, ext='short_circuit', dst='/bin/true'):
    fullpath = os.path.join(root.rstrip('/'), cmd.lstrip('/'))
    if os.path.isfile(fullpath):
        try:
            log.debug('Short circuiting {0}'.format(fullpath))
            os.rename(fullpath, '{0}.{1}'.format(fullpath, ext))
            log.debug('{0} renamed to {0}.{1}'.format(fullpath, ext))
            os.symlink(dst, fullpath)
            log.debug('{0} linked to {1}'.format(fullpath, dst))
        except Exception:
            log.exception('Error encountered while short circuiting {0} to {1}'.format(fullpath, dst))
            return False
        else:
            log.debug('short circuited {0} to {1}'.format(fullpath, dst))
            return True
    else:
        log.error('{0} not found'.format(fullpath))
        return False


def short_circuit_files(root, cmds, ext='short_circuit', dst='/bin/true'):
    for cmd in cmds:
        if not short_circuit(root, cmd, ext, dst):
            return False
    return True


def rewire(root, cmd, ext='short_circuit'):
    fullpath = os.path.join(root.rstrip('/'), cmd.lstrip('/'))
    if os.path.isfile('{0}.{1}'.format(fullpath, ext)):
        try:
            log.debug('Rewiring {0}'.format(fullpath))
            os.remove(fullpath)
            os.rename('{0}.{1}'.format(fullpath, ext), fullpath)
            log.debug('{0} rewired'.format(fullpath))
        except Exception:
            log.exception('Error encountered while rewiring {0}'.format(fullpath))
            return False
        else:
            log.debug('rewired {0}'.format(fullpath))
            return True
    else:
        log.error('{0}.{1} not found'.format(fullpath, ext))
        return False


def rewire_files(root, cmds, ext='short_circuit'):
    for cmd in cmds:
        if not rewire(root, cmd, ext):
            return False
    return True


def mkdir_p(path):
    try:
        if os.path.isdir(path):
            return

        os.makedirs(path)
    except OSError as e:
        if e.errno == errno.EEXIST:
            pass
        else:
            raise e
