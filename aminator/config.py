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

import yaml
import os
import logging

log = logging.getLogger(__name__)


__doc__ = """
# aminator default configuration settings
# This document is processed by yaml and formatted per
# http://pyyaml.org/wiki/PyYAMLDocumentation#Documents

config_file: /etc/aminator    # defaults can be overridden in this yaml formatted file.
lockdir: /var/lock            # lock file directory

device_prefixes: [sd, xvd]             # possible OS device prefixes
minor_device_letters: 'fghijklmnop'    # devices used for non-partitioned volumes
major_device_letters: 'qrstuvwxyz'     # devices used for partitioned volumes

volume_root: /aminator/volumes      # volumes mounted onto subdirs of this director.
bind_mounts: [/dev, /proc, /sys]    # each of these are bind mounted to it's counterpart
                                    # under the root of the mounted volume.

logdir: /var/log              # destination for debug log files

# elements contained the URL of the 'Detailed logs' console message
log_url_prefix: "http://localhost:80/"
"""


class Config(object):
    def __init__(self):
        file_config = {}
        default_cfg = yaml.load(__doc__)
        self._set_attrs(**default_cfg)
        if os.path.exists(self.config_file):
            with open(self.config_file) as cf:
                try:
                    file_config = yaml.load(cf)
                except yaml.MarkedYAMLError, e:
                    log.debug("{0}: {1}: line{2}, column{3}".format(e,
                                                                    e.message,
                                                                    e.problem_mark.line,
                                                                    e.problem_mark.column))
        if len(file_config) > 0:
            self._set_attrs(**file_config)

    def _set_attrs(self, **kwargs):
        for i in kwargs:
            value = kwargs[i]
            if isinstance(value, list):
                value = tuple(value)
            setattr(self, i, value)

config = Config()
