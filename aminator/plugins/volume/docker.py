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
aminator.plugins.volume.docker
=============================
docker volume allocator
"""
import logging

from aminator.plugins.volume.base import BaseVolumePlugin
from aminator.config import conf_action

__all__ = ('DockerVolumePlugin',)
log = logging.getLogger(__name__)


class DockerVolumePlugin(BaseVolumePlugin):
    _name = 'docker'

    def add_plugin_args(self, *args, **kwargs):
        context = self._config.context
        docker = self._parser.add_argument_group(title='Docker')
        docker.add_argument('-D', '--docker-root', dest='docker_root',
                              action=conf_action(config=context.cloud), default="/var/lib/docker",
                              help='The base directory for docker containers')
        return docker

    def __enter__(self):
        self._cloud.allocate_base_volume()
        self._cloud.attach_volume(self._blockdevice)
        container = self._config.context.cloud["container"]
        # FIXME this path should be configurable
        mountpoint = "{}/aufs/mnt/{}".format(self._config.context.cloud["docker_root"], container)
        self._config.context.volume["mountpoint"] = mountpoint
        return mountpoint

    def __exit__(self, exc_type, exc_value, trace):
        if exc_type: log.exception("Exception: {0}: {1}".format(exc_type.__name__,exc_value))
        if exc_type and self._config.context.get("preserve_on_error", False):
            return False
        self._cloud.detach_volume(self._blockdevice)
        self._cloud.delete_volume()
        return False
