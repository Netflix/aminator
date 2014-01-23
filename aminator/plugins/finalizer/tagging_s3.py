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
aminator.plugins.finalizer.tagging_s3
======================================
s3 tagging image finalizer
"""
import logging
from shutil import rmtree
from os.path import isdir
from os import makedirs, system

from aminator.config import conf_action
from aminator.plugins.finalizer.tagging_base import TaggingBaseFinalizerPlugin
from aminator.util.linux import sanitize_metadata, command

__all__ = ('TaggingS3FinalizerPlugin',)
log = logging.getLogger(__name__)


class TaggingS3FinalizerPlugin(TaggingBaseFinalizerPlugin):
    _name = 'tagging_s3'

    def add_plugin_args(self):
        tagging = super(TaggingS3FinalizerPlugin,self).add_plugin_args()
        
        context = self._config.context
        tagging.add_argument('-n', '--name', dest='name', action=conf_action(context.ami),
                             help='name of resultant AMI (default package_name-version-release-arch-yyyymmddHHMM-s3')

        tagging.add_argument('--cert', dest='cert', action=conf_action(context.ami),
                             help='The path to the PEM encoded RSA public key certificate file for ec2-bundle-volume')
        tagging.add_argument('--privatekey', dest='privatekey', action=conf_action(context.ami),
                             help='The path to the PEM encoded RSA private key file for ec2-bundle-vol')
        tagging.add_argument('--ec2-user', dest='ec2_user', action=conf_action(context.ami),
                             help='ec2 user id for ec2-bundle-vol')
        tagging.add_argument('--tmpdir', dest='tmpdir', action=conf_action(context.ami),
                             help='temp directory used by ec2-bundle-vol')
        tagging.add_argument('--bucket', dest='bucket', action=conf_action(context.ami),
                             help='the S3 bucket to use for ec2-upload-bundle')
        tagging.add_argument('--break-copy-volume', dest='break_copy_volume', action=conf_action(context.ami, action='store_true'),
                             help='break into shell after copying the volume, for debugging')

    def _set_metadata(self):
        super(TaggingS3FinalizerPlugin, self)._set_metadata()
        context = self._config.context
        config = self._config.plugins[self.full_name]
        metadata = context.package.attributes
        ami_name = context.ami.get('name', None)
        if not ami_name:
            ami_name = config.name_format.format(**metadata)

        context.ami.name = sanitize_metadata('{0}-s3'.format(ami_name))

    def tmpdir(self):
        config = self._config.plugins[self.full_name]
        ami = self._config.context.ami
        return "{}/{}".format(ami.get("tmpdir", config.get("default_tmpdir", "/tmp")), ami.name)

    def image_location(self):
        context = self._config.context
        return "{}/{}".format(self.tmpdir(), context.ami.name)

    @command()
    def _copy_volume(self):
        context = self._config.context
        tmpdir=self.tmpdir()
        if not isdir(tmpdir):
            makedirs(tmpdir)
        return ["dd", "bs=65536", "if={}".format(context.volume.dev), "of={}".format(self.image_location())]

    @command()
    def _bundle_image(self):
        context = self._config.context

        config = self._config.plugins[self.full_name]
        block_device_map = config.default_block_device_map
        root_device = config.default_root_device

        bdm = "root={}".format(root_device)
        for bd in block_device_map:
            bdm += ",{}={}".format(bd[1],bd[0])
        bdm += ",ami={}".format(root_device)
        
        cmd = ['ec2-bundle-image']
        cmd.extend(['-c', context.ami.get("cert", config.default_cert)])
        cmd.extend(['-k', context.ami.get("privatekey", config.default_privatekey)])
        cmd.extend(['-u', context.ami.get("ec2_user", str(config.default_ec2_user))])
        cmd.extend(['-i', self.image_location()])
        cmd.extend(['-d', self.tmpdir()])
        if context.base_ami.architecture:
            cmd.extend(['-r', context.base_ami.architecture])
        if context.base_ami.kernel_id:
            cmd.extend(['--kernel', context.base_ami.kernel_id])
        if context.base_ami.ramdisk_id:
            cmd.extend(['--ramdisk', context.base_ami.ramdisk_id])
        cmd.extend(['-B', bdm])
        return cmd

    @command()
    def _upload_bundle(self):
        context = self._config.context

        provider = self._cloud._connection.provider
        ak = provider.get_access_key()
        sk = provider.get_secret_key()
        tk = provider.get_security_token()

        cmd = ['ec2-upload-bundle']
        cmd.extend(['-b', context.ami.bucket])
        cmd.extend(['-a', ak])
        cmd.extend(['-s', sk])
        if tk:
            cmd.extend(['-t', tk])
        cmd.extend(['-m', "{0}.manifest.xml".format(self.image_location())])
        cmd.extend(['--retry'])
        return cmd

    def _register_image(self):
        context = self._config.context
        log.info('Registering image')
        if not self._cloud.register_image(manifest="{}/{}.manifest.xml".format(context.ami.bucket,context.ami.name)):
            return False
        log.info('Registration success')
        return True

    def finalize(self):
        log.info('Finalizing image')
        context = self._config.context
        self._set_metadata()

        ret = self._copy_volume()
        if not ret.success: # pylint: disable=no-member
            log.debug('Error copying volume, failure:{0.command} :{0.std_err}'.format(ret.result))
            return False

        if context.ami.get('break_copy_volume', False):
            system("bash")
            
        ret = self._bundle_image()
        if not ret.success: # pylint: disable=no-member
            log.debug('Error bundling image, failure:{0.command} :{0.std_err}'.format(ret.result))
            return False

        ret = self._upload_bundle()
        if not ret.success: # pylint: disable=no-member
            log.debug('Error uploading bundled volume, failure:{0.command} :{0.std_err}'.format(ret.result))
            return False

        if not self._register_image():
            log.critical('Error registering image')
            return False

        if not self._add_tags(['ami']):
            log.critical('Error adding tags')
            return False

        log.info('Image registered and tagged')
        self._log_ami_metadata()
        return True

    def __exit__(self, exc_type, exc_value, trace):
        if exc_type: log.exception("Exception: {0}: {1}".format(exc_type.__name__,exc_value))
        # delete tmpdir used by ec2-bundle-vol
        td = self.tmpdir()
        if isdir(td):
            rmtree(td)
        return False
                            
