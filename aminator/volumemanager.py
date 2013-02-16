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

import boto
import boto.ec2

from aminator.devicemanager import DeviceManager
from aminator.exceptions import VolumeError
from aminator.utils import this_instance, ec2connection, retry, mount, unmount, os_node_exists, snapshot_complete


log = logging.getLogger(__name__)
# TODO: this should be configurable
ovenroot = '/aminator/oven'
pid = str(os.getpid())


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
        self._unmount()
        self.snapshot = self.create_snapshot(description)
        if not snapshot_complete(self.snapshot):
            raise VolumeError('time out waiting for %s to complete' % self.snapshot.id)
        self._mount()
        log.debug('%s created' % self.snapshot.id)

    def __enter__(self):
        self._attach()
        self._mount()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self._unmount()
        self._detach()
        self._delete()

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
    def _attach(self):
        # attachments time out after 255 seconds. we'll try this twice.
        self._newvol()
        with DeviceManager() as dev:
            log.debug('attaching %s to %s:%s' % (self.id, this_instance.id, dev.node))
            self.dev = dev.node
            self.attach(this_instance.id, dev.node)
            if not self.attached:
                log.debug('{} attachment to {} timed out'.format(self.vol.id, self.dev))
                self.vol.add_tag('status', value='used')
                # this triggers the retry
                raise VolumeError("Timed out waiting for volume to attach")
        log.debug('{} attached to {}'.format(self.id, self.dev))
        self.mnt = os.path.join(ovenroot, os.path.basename(self.dev))
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

    def _detach(self):
        log.debug('detaching %s' % self.id)
        self.detach()
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

    def _mount(self):
        if not mount(self.dev, self.mnt):
            raise VolumeError('%s: mount failure' % self.dev)
        log.debug('%s mounted on %s' % (self.id, self.mnt))

    @retry(VolumeError, tries=3, delay=1, backoff=2, logger=log)
    def _unmount(self):
        log.debug('unmounting %s from %s' % (self.dev, self.mnt))
        if not unmount(self.dev):
            raise VolumeError('%s: unmount failure' % self.dev)
        log.debug('%s unmounted from %s' % (self.id, self.mnt))

    def _delete(self):
        log.debug('deleting %s' % self.id)
        self.delete()

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
