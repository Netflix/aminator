# -*- coding: utf-8 -*-

#
#
#  Copyright 2013 Netflix
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
aminator.plugins.provisioner.apt_script
================================
"""
import logging
from collections import namedtuple
import re
from aminator.plugins.provisioner.apt import AptProvisionerPlugin
from aminator.util.linux import command
from aminator.util.linux import Chroot

__all__ = ('AptScriptProvisionerPlugin',)
log = logging.getLogger(__name__)

CommandResult = namedtuple('CommandResult', 'success result')
CommandOutput = namedtuple('CommandOutput', 'std_out std_err')


class AptScriptProvisionerPlugin(AptProvisionerPlugin):
    """
    AptChefProvisionerPlugin takes the majority of its behavior from AptProvisionerPlugin
    See AptProvisionerPlugin for details
    """
    _name = 'apt_script'

    def _store_package_metadata(self):
        """
        save info for the AMI we're building in the context so that it can be incorporated into tags and the description
        during finalization.
        """
        context = self._config.context
        context.package.attributes = {'version': "", 'release': "", 'name': context.package.arg}

    def provision(self):
        """
        overrides the base provision
          * Download the script if the path starts with "http" otherwise copy it from the local fs
          * Run the script
        """
        log.debug('Entering chroot at {0}'.format(self._mountpoint))

        context = self._config.context
        script_src = context.package.arg
        script_dst = '/root/aminator-script'

        if re.search("^http", script_src ):
            log.debug('Downloading script: ' + script_src)
            wget(script_src, self._mountpoint + script_dst)
        else:
            cp(script_src,  self._mountpoint + script_dst)
        with Chroot(self._mountpoint):
            log.debug('Inside chroot')
            log.debug('Running script')
            make_executable(script_dst)
            run_script(script_dst)
        log.debug('Exited chroot')
        self._store_package_metadata()
        log.info('Provisioning succeeded!')
        return True

@command()
def mkdirs(dir):
    return 'mkdir -p {0}'.format(dir)

@command()
def wget(url, file):
    return 'wget {0} -O {1}'.format(url, file)

@command()
def make_executable(path):
    return 'chmod +x {0}'.format(path)

@command()
def cp(src_path,dest_path):
    return 'cp {0} {1}'.format(src_path,dest_path)

@command()
def run_script(path):
    return '{0}'.format(path)
