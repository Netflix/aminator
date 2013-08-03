# -*- coding: utf-8 -*-
#
#  Copyright 2013 Answers for AWS LLC
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

"""
aminator.plugins.provisioner.ansible
================================
Ansible provisioner
"""
import logging
import os
import shutil

from aminator.config import conf_action
from aminator.plugins.provisioner.linux import BaseLinuxProvisionerPlugin
from aminator.util.linux import apt_get_install, command, Chroot

__all__ = ('AnsibleProvisionerPlugin',)
log = logging.getLogger(__name__)


class AnsibleProvisionerPlugin(BaseLinuxProvisionerPlugin):
    """
    AnsibleProvisionerPlugin takes the majority of its behavior from BaseLinuxProvisionerPlugin
    See BaseLinuxProvisionerPlugin for details
    """
    _name = 'ansible'
    
    def add_plugin_args(self):
        """ Add Ansible specific variables """
        
        ansible_config = self._parser.add_argument_group(title='Ansible Options', description='Options for the Ansible provisioner')
        
        ansible_config.add_argument('-ev', '--extra-vars', dest='extravars', help='A set of additional key=value variables to be used in the playbook',
                                 action=conf_action(self._config.plugins[self.full_name]))

    def provision(self):
        log.debug("PAS: provision")
        context = self._config.context

        log.debug('Pre chroot command block')
        self._pre_chroot_block()

        log.debug('Entering chroot at {0}'.format(self._mountpoint))

        with Chroot(self._mountpoint):
            log.debug('Inside chroot')

            result = self._write_local_inventory()
            if not result:
                log.critical('Could not write local inventory file: {0.std_err}'.format(result.result))
                return False

            result = self._provision_package()
            if not result.success:
                log.critical('Installation of {0} failed: {1.std_err}'.format(context.package.arg, result.result))
                return False
            self._store_package_metadata()

        log.debug('Exited chroot')

        log.debug('Post chroot command block')
        self._post_chroot_block()

        log.info('Provisioning succeeded!')
        return True
    
    def _write_local_inventory(self):
        """ Writes a local inventory file inside the chroot environment """

        context = self._config.context
        config = self._config.plugins[self.full_name]
        path = config.get('inventory_file_path', '/etc/ansible')
        filename = path + "/" + config.get('inventory_file')
        context.package.inventory = filename
        
        if not os.path.isdir(path):
            log.debug("creating %s", path)
            os.makedirs(path)
            log.debug("created %s", path)

        with open(filename, 'w') as f:
            log.debug("writing %s", filename)
            f.write(config.get('inventory_file_content'))
            log.debug("wrote %s", filename)

        return True
    
    def _pre_chroot_block(self):
        """ run commands after mounting the volume, but before chroot'ing """
        self._copy_playbooks()
    
    def _copy_playbooks(self):
        """ Copies all playbook files from the aminator server to the chroot environment """

        config = self._config.plugins[self.full_name]
        playbooks_path_source = config.get('playbooks_path_source')
        playbooks_path_dest = self._mountpoint + config.get('playbooks_path_dest')
        
        if not os.path.isdir(playbooks_path_source):
            log.critical("directory does not exist %s", playbooks_path_source)
            
        if os.path.isdir(playbooks_path_dest):
            log.critical("directory already exists %s", playbooks_path_dest)
            return False

        shutil.copytree(playbooks_path_source, playbooks_path_dest)

        return True

    def _provision_package(self):
        log.debug("PAS: _provision_package")
        context = self._config.context
        config = self._config.plugins[self.full_name]
        extra_vars = config.get('extravars', '')
        path = config.get('playbooks_path_dest')

        return run_ansible_playbook(context.package.inventory, extra_vars, path, context.package.arg)

    def _store_package_metadata(self):
        log.debug("PAS: _store_package_metadata")
        context = self._config.context
        config = self._config.plugins[self.full_name]
        metadata = {}
        metadata['name'] = context.package.arg
        metadata['version'] = ''
        metadata['release'] = ''
        metadata['extra_vars'] = config.get('extravars', '')
        context.package.attributes = metadata

    def _refresh_package_metadata(self):
        """ Empty until Aminator is reorganized - end of August 2013 """
        return True
    
    def _deactivate_provisioning_service_block(self):
        """ Empty until Aminator is reorganized - end of August 2013 """
        return True

    def _activate_provisioning_service_block(self):
        """ Empty until Aminator is reorganized - end of August 2013 """
        return True


@command()
def run_ansible_playbook(inventory, extra_vars, dir, playbook):
    log.debug("PAS: run_ansible_playbook: (%s, %s, %s)", inventory, extra_vars, playbook)
    return 'ansible-playbook -c local -i {0} -e \\\'ami_build=True {1}\\\' {2}'.format(inventory, extra_vars, dir + '/' + playbook)

