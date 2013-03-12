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

import logging
import os
import re

import boto
import boto.ec2

from aminator.clouds.ec2.core import ec2connection
from aminator.clouds.ec2.instanceinfo import this_instance
from aminator.clouds.ec2.utils import snapshot_complete
from aminator.config import config
from aminator.device import device
from aminator.exceptions import VolumeError
from aminator.utils import retry, chroot_setup, chroot_teardown, os_node_exists, native_device_prefix


log = logging.getLogger(__name__)


class VolumeManager(boto.ec2.volume.Volume):
    """
    Provide EBS volume created from the snapshot of a particular AMI. Intended to be used in a "with" context.
    Upon entering the context, the volume is available through self.mnt for chroot'ed commands.
    Exiting the context unmounts, detaches, and deletes the volume
    """
    def __init__(self, ami=None):
        """
        :type ami: class:`boto.ec2.image.Image`
        :param ami: the source ami
        """
        assert isinstance(ami, boto.ec2.image.Image), "ami paramater is %s, not boto.ec2.image.Image." % str(type(ami))
        assert ami.root_device_type == 'ebs', "%s (%s) is not an EBS AMI." % (ami.name, ami.id)
        self.ami = ami
        self.mnt = None
        self.dev = None
        self.snapshot = None
        self.rootdev = ami.block_device_mapping[ami.root_device_name]
        self.ami_metadata = {"base_ami_id": self.ami.id,
                             "base_ami_snapshot": self.rootdev.snapshot_id,
                             "arch": self.ami.architecture,
                             "aki": self.ami.kernel_id,
                             "base_ami_name": self.ami.name,
                             "ari": self.ami.ramdisk_id,
                             "base_ami_version": self.ami.tags['base_ami_version']}
        boto.ec2.volume.Volume.__init__(self, connection=ec2connection())

    def add_snap(self, description=""):
        """ Create a snapshot of this volume.
        """
        log.debug('creating snapshot from  %s with description %s' % (self.id, description))
        self.unmount()
        self.snapshot = self.create_snapshot(description)
        if not snapshot_complete(self.snapshot):
            raise VolumeError('time out waiting for %s to complete' % self.snapshot.id)
        log.debug('%s created' % self.snapshot.id)

    def __enter__(self):
        self.attach()
        self.mount()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.unmount()
        self.detach()
        self.delete()

    def _newvol(self):
        self.id = self.connection.create_volume(self.rootdev.size, this_instance.az, self.rootdev.snapshot_id).id
        self.connection.create_tags([self.id], {"purpose": "amibake",
                                                "status": "busy",
                                                "ami": self.ami.id,
                                                "ami-name": self.ami.name,
                                                "arch": self.ami.architecture})
        self.update()
        log.debug('%s created' % self.id)

    @retry(VolumeError, tries=2, delay=1, backoff=2, logger=log)
    def attach(self):
        # attachments time out after 255 seconds. we'll try this twice.
        self._newvol()
        with device() as dev:
            self.dev = dev
            dev_to_attach = dev

            if native_device_prefix() == 'xvd':
                dev_to_attach = re.sub('xvd', 'sd', dev.node)
                attach_msg = 'attaching {} to {}:{} ({})'.format(self.id,
                                                                 this_instance.id,
                                                                 dev,
                                                                 dev_to_attach)
            else:
                attach_msg = 'attaching {} to {}:{}'.format(self.id,
                                                            this_instance.id,
                                                            dev)
            log.debug(attach_msg)
            super(VolumeManager, self).attach(this_instance.id, dev_to_attach)

            if not self.attached:
                log.debug('{} attachment to {} timed out'.format(self.vol.id, dev_to_attach))
                self.vol.add_tag('status', value='used')
                # this triggers the retry
                raise VolumeError("Timed out waiting for volume to attach")

        log.debug('{} attached to {}'.format(self.id, self.dev))
        self.mnt = os.path.join(config.volume_root, os.path.basename(self.dev))
        if not os.path.exists(self.mnt):
            os.makedirs(self.mnt)
        return True

    @property
    def attached(self):
        try:
            self._attached()
        except VolumeError:
            log.debug('Time out waiting for volume to attach')
            return False
        return True

    @retry(VolumeError, tries=10, delay=1, backoff=2, logger=log)
    def _attached(self):
        status = self.update()
        if status != 'in-use':
            raise VolumeError("{} not yet attached.".format(self.id))
        elif not os_node_exists(self.dev):
            raise VolumeError("{} doesn't exist yet.".format(self.dev))
        else:
            return True

    def detach(self):
        log.debug('detaching %s' % self.id)
        super(VolumeManager, self).detach()
        if not self._detached():
            raise VolumeError('time out waiting for %s to detach from %s' % (self.vol.id, self.dev))
        log.debug('%s detached' % self.id)

    @retry(VolumeError, tries=7, delay=1, backoff=2, logger=log)
    def _detached(self):
        status = self.update()
        if status != 'available':
            raise VolumeError("%s not yet detached." % self.id)
        elif os_node_exists(self.dev):
            raise VolumeError("%s still exists." % self.dev)
        else:
            return True

    def mount(self):
        if not chroot_setup(self.mnt, self.dev):
            raise VolumeError('Mount failure for {0}({1})'.format(self.mnt, self.dev))
        log.debug('%s mounted on %s' % (self.id, self.mnt))

    @retry(VolumeError, tries=3, delay=1, backoff=2, logger=log)
    def unmount(self):
        log.debug('unmounting %s from %s' % (self.dev, self.mnt))
        if not chroot_teardown(self.mnt):
            raise VolumeError('%s: unmount failure' % self.mnt)
        log.debug('%s unmounted from %s' % (self.id, self.mnt))

    def delete(self):
        log.debug('deleting %s' % self.id)
        super(VolumeManager, self).delete()

    @property
    def deleted(self):
        """Has the volume been deleted from EC2?"""
        try:
            self.update()
        except boto.exception.EC2ResponseError, e:
            if e.code == 'InvalidVolume.NotFound':
                log.debug('%s deleted' % self.id)
                return True
        return False
