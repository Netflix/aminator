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
aminator.plugins.provisioner.base
==================================
Simple base class for cases where there are small distro-specific corner cases
"""
import abc
import logging
import os
import shutil

from glob import glob

from aminator.config import conf_action
from aminator.plugins.base import BasePlugin
from aminator.util import download_file
from aminator.util.linux import Chroot, monitor_command
from aminator.util.metrics import fails, lapse

__all__ = ('BaseProvisionerPlugin',)
log = logging.getLogger(__name__)


class BaseProvisionerPlugin(BasePlugin):
    """
    Most of what goes on between apt and yum provisioning is the same, so we factored that out,
    leaving the differences in the actual implementations
    """
    __metaclass__ = abc.ABCMeta
    _entry_point = 'aminator.plugins.provisioner'

    @abc.abstractmethod
    def _provision_package(self):
        """ subclasses must implement package provisioning logic """

    @abc.abstractmethod
    def _store_package_metadata(self):
        """ stuff name, version, release into context """

    def _pre_chroot_block(self):
        """ run commands before entering chroot"""
        pass

    def _post_chroot_block(self):
        """ commands to run after the exiting the chroot"""
        pass

    def add_plugin_args(self, *args, **kwargs):
        context = self._config.context
        prov = self._parser.add_argument_group(title='Provisioning')
        prov.add_argument("-i", "--interactive", dest='interactive', help="interactive session after provivioning", action=conf_action(config=context.package, action="store_true"))

    def provision(self):
        context = self._config.context

        if self._local_install():
            log.info('performing a local install of {0}'.format(context.package.arg))
            context.package.local_install = True
            if not self._stage_pkg():
                log.critical('failed to stage {0}'.format(context.package.arg))
                return False
        else:
            log.info('performing a repo install of {0}'.format(context.package.arg))
            context.package.local_install = False

        log.debug('Pre chroot command block')
        self._pre_chroot_block()

        log.debug('Entering chroot at {0}'.format(self._distro._mountpoint))

        with Chroot(self._distro._mountpoint):
            log.debug('Inside chroot')

            result = self._provision_package()

            if context.package.get('interactive', False):
                os.system("bash")

            if not result.success:
                log.critical('Installation of {0} failed: {1.std_err}'.format(context.package.arg, result.result))
                return False
            self._store_package_metadata()
            if context.package.local_install and not context.package.get('preserve', False):
                os.remove(context.package.arg)

            # run scripts that may have been delivered in the package
            scripts_dir = self._config.plugins[self.full_name].get('scripts_dir', '/var/local')
            log.debug('scripts_dir = {0}'.format(scripts_dir))

            if scripts_dir:
                if not self._run_provision_scripts(scripts_dir):
                    return False

        log.debug('Exited chroot')

        log.debug('Post chroot command block')
        self._post_chroot_block()

        log.info('Provisioning succeeded!')
        return True

    @fails("aminator.provisioner.provision_scripts.error")
    @lapse("aminator.provisioner.provision_scripts.duration")
    def _run_provision_scripts(self, scripts_dir):
        """
        execute every python or shell script found in scripts_dir
            1. run python or shell scripts in lexical order

        :param scripts_dir: path in chroot to look for python and shell scripts
        :return: None
        """

        script_files = sorted(glob(scripts_dir + '/*.py') + glob(scripts_dir + '/*.sh'))
        if not script_files:
            log.debug("no python or shell scripts found in {0}".format(scripts_dir))
        else:
            log.debug('found scripts {0} in {1}'.format(script_files, scripts_dir))
            for script in script_files:
                log.debug('executing script {0}'.format(script))
                if os.access(script, os.X_OK):
                    # script is executable, so just run it
                    result = run_script(script)
                else:
                    if script.endswith('.py'):
                        result = run_script(['python', script])
                    else:
                        result = run_script(['sh', script])
                if not result.success:
                    log.critical("script failed: {0}: {1.std_err}".format(script, result.result))
                    return False
        return True

    def _local_install(self):
        """True if context.package.arg ends with a package extension
        """
        config = self._config
        ext = config.plugins[self.full_name].get('pkg_extension', '')
        if not ext:
            return False

        # ensure extension begins with a dot
        ext = '.{0}'.format(ext.lstrip('.'))

        return config.context.package.arg.endswith(ext)

    def _stage_pkg(self):
        """copy package file into AMI volume.
        """
        context = self._config.context
        context.package.file = os.path.basename(context.package.arg)
        context.package.full_path = os.path.join(self._distro._mountpoint, context.package.dir.lstrip('/'), context.package.file)
        try:
            if any(protocol in context.package.arg for protocol in ['http://', 'https://']):
                self._download_pkg(context)
            else:
                self._move_pkg(context)
        except Exception:
            errstr = 'Exception encountered while staging package'
            log.critical(errstr)
            log.debug(errstr, exc_info=True)
            return False
            # reset to chrooted file path
        context.package.arg = os.path.join(context.package.dir, context.package.file)
        return True

    def _download_pkg(self, context):
        """dowload url to context.package.dir
        """
        pkg_url = context.package.arg
        dst_file_path = context.package.full_path
        log.debug('downloading {0} to {1}'.format(pkg_url, dst_file_path))
        download_file(pkg_url, dst_file_path, context.package.get('timeout', 1), verify_https=context.get('verify_https', False))

    def _move_pkg(self, context):
        src_file = context.package.arg.replace('file://', '')
        dst_file_path = context.package.full_path
        shutil.move(src_file, dst_file_path)

    def __call__(self, distro):
        self._distro = distro
        return self


def run_script(script):
    return monitor_command(script)
