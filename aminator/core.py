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
from datetime import datetime

from boto.ec2.blockdevicemapping import BlockDeviceType
from boto.ec2.image import Image

from aminator.clouds.ec2.core import ec2connection
from aminator.clouds.ec2.utils import default_block_device_map, ROOT_BLOCK_DEVICE
from aminator.clouds.ec2.utils import register, add_tags
from aminator.packagefetcher import PackageFetcher
from aminator.utils import shlog
from aminator.volumemanager import VolumeManager

log = logging.getLogger(__name__)


class AminateRequest(object):
    def __init__(self, pkg, baseami, ami_suffix, creator, wants_ebs=True, ami_name=None):
        log.info('looking up package %s' % pkg)
        self.fetcher = PackageFetcher(pkg)
        self.base = baseami
        self.tags = {}
        self.snapshot_tags = {}
        self.ami = None
        self.wants_ebs = wants_ebs
        self.name = ami_name
        self.suffix = ami_suffix
        self.vol = None
        self.description = ""
        self.tags['creator'] = creator
        self.snapshot_tags['creator'] = creator

    def aminate(self):
        with VolumeManager(self.base) as vol:
            log.info("aminating %s with base AMI %s on %s attached to %s and mounted on %s" %
                    (self.fetcher.rpmfile, vol.ami.name, vol.id, vol.dev, vol.mnt))
            self.vol = vol
            self.mnt = vol.mnt
            if self.install() is not True:
                log.error('package installation failed.')
                return False
            log.info('%s installation complete.' % self.fetcher.rpmfile)
            self._set_attrs()
            log.info('creating snapshot')
            vol.add_snap(self.description)
            log.info('%s: snapshot complete' % vol.snapshot.id)
            if self.finish() is not True:
                log.error('amination failed.')
                return False
        if self.vol.deleted:
            log.debug('%s deleted' % self.vol.id)
        else:
            log.debug('%s has not been deleted.' % self.vol.id)
        return True

    def install(self):
        """ install self.pkg onto the file system rooted in self.mnt
        """
        self.fetcher.fetch("%s/var/cache" % (self.mnt))
        return shlog("/usr/bin/aminator.sh -a install {} {}".format(self.mnt, self.fetcher.rpmfilepath))

    def finish(self, block_device_map=None):
        # register the snapshot
        # tag the ami and snapshot
        if block_device_map is None:
            block_device_map = default_block_device_map()

        block_device_map[ROOT_BLOCK_DEVICE] = BlockDeviceType(snapshot_id=self.vol.snapshot.id,
                                                              delete_on_termination=True)
        ami = Image(ec2connection())
        ami_name = '{}-ebs'.format(self.name)
        ami = register(name=ami_name,
                       description=self.description,
                       architecture=self.vol.ami_metadata['arch'],
                       block_device_map=block_device_map,
                       root_device_name=ROOT_BLOCK_DEVICE,
                       kernel_id=self.vol.ami_metadata['aki'],
                       ramdisk_id=self.vol.ami_metadata['ari'])

        if ami is not None:
            log.info('AMI registered: %s %s' % (ami.id, ami.name))
            self.ami = ami
            self.tags['creation_time'] = datetime.utcnow().strftime('%F %T UTC')
            self.snapshot_tags['ami-id'] = ami.id

            add_tags([ami.id], self.tags)
            ami.update()
            for k in ami.tags:
                log.info('TAG\timage\t%s\t%s\t%s' % (ami.id, k, ami.tags[k]))

            add_tags([self.vol.snapshot.id], self.snapshot_tags)
            self.vol.snapshot.update()
            for k in self.vol.snapshot.tags:
                log.debug('TAG\tsnapshot\t%s\t%s\t%s' % (self.vol.snapshot.id, k, self.vol.snapshot.tags[k]))

        return self.ami is not None

    def _set_attrs(self):
        self.tags['appversion'] = self.fetcher.appversion
        self.snapshot_tags['appversion'] = self.fetcher.appversion
        self.tags['base_ami_version'] = self.vol.ami_metadata['base_ami_version']
        if self.name is None:
            self.name = "%s-%s-%s" % (self.fetcher.name_ver_rel, self.vol.ami_metadata['arch'], self.suffix)
        self.description = "name=%s, arch=%s, ancestor_name=%s, ancestor_id=%s, ancestor_version=%s" % (
                            self.name, self.vol.ami_metadata['arch'],
                            self.vol.ami_metadata['base_ami_name'],
                            self.vol.ami_metadata['base_ami_id'],
                            self.vol.ami_metadata['base_ami_version'])
