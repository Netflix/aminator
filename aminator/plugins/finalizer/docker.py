# -*- coding: utf-8 -*-

#
#
#  Copyright 2014 Netflix, Inc.
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
aminator.plugins.finalizer.docker
======================================
docker image finalizer
"""
import logging
from aminator.plugins.finalizer.base import BaseFinalizerPlugin
from aminator.util.linux import sanitize_metadata
from aminator.config import conf_action
from os import environ
from datetime import datetime

__all__ = ('DockerFinalizerPlugin',)
log = logging.getLogger(__name__)


class DockerFinalizerPlugin(BaseFinalizerPlugin):
    _name = 'docker'

    def add_plugin_args(self):
        context = self._config.context
        docker = self._parser.add_argument_group(title='Docker Naming',
                                                  description='Naming options for the resultant Docker image')
        docker.add_argument('-I', '--image-name', dest='name', action=conf_action(context.ami),
                             help='docker image name')
        docker.add_argument('-s', '--suffix', dest='suffix', action=conf_action(context.ami),
                             help='suffix of docker image name, (default yyyymmddHHMM)')
        return docker


    def _set_metadata(self):
        context = self._config.context
        config = self._config.plugins[self.full_name]

        log.debug('Populating snapshot and docker image metadata naming')

        metadata = context.package.attributes

        suffix = context.ami.get('suffix', None)
        if not suffix:
            suffix = config.suffix_format.format(datetime.utcnow())

        metadata['suffix'] = suffix

        name = context.ami.get('name', None)
        if not name:
            name = config.name_format.format(**metadata)

        context.ami.name = sanitize_metadata('{0}'.format(name))

    def finalize(self):
        """ finalize an image """
        self._set_metadata()
        log.info('Taking a snapshot of the target volume')
        if not self._cloud.snapshot_volume():
            return False
        log.info('Snapshot success')

        log.info('Registering image')
        if not self._cloud.register_image():
            return False
        log.info('Registration success')
        return True


    def __enter__(self):
        context = self._config.context
        if context.ami.get("suffix",None):
            environ["AMINATOR_DOCKER_SUFFIX"] = context.ami.suffix
        return self

    def __exit__(self, exc_type, exc_value, trace):
        if exc_type: log.exception("Exception: {0}: {1}".format(exc_type.__name__,exc_value))
        return False

    def __call__(self, cloud):
        self._cloud = cloud
        return self
