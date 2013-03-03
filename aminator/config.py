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
import sys


__doc__ = """
# aminator default configuration settings
# This document is processed by yaml and formatted per
# http://pyyaml.org/wiki/PyYAMLDocumentation#Documents

config_file: /etc/aminator    # defaults can be overridden in this yaml formatted file.
lockdir: /var/lock            # lock file directory

device_prefixes: [sd, xvd]                      # possible OS device prefixes
nonpartitioned_device_letters: 'fghijklmnop'    # devices used for non-partitioned volumes
partitioned_device_letters:    'qrstuvwxyz'     # devices used for partitioned volumes, i.e. hvm

volume_root: /aminator/volumes      # volumes mounted onto subdirs of this director.
bind_mounts: [/dev, /proc, /sys]    # each of these are bind mounted to it's counterpart
                                    # under the root of the mounted volume.

root_device: /dev/sda1
ephemeral_devices:
    - /dev/sdb
    - /dev/sdc
    - /dev/sdd
    - /dev/sde

# log_dir: destination for debug log files. Debug logs are interesting as they include all the
# gory details of the aminate execution. Debug {logfile} names are constructued using the
# command-line package and AMI suffix parameters and take the form: {package}-{suffix}.log
log_dir: /var/log

# log_url_prefix: should include two formatting replacement fields to be replaced
# with the public dns name (or ip address if in vpc) of the instance where aminate
# is executed and the detailed log.
# eg. http://{name_or_address}:8080/some/path/{logfile}
log_url_prefix:

# boto_logdir: Directory where boto debug logs will be written. Log file paths take this form:
# {boto_logdir}/{boto}-{logilfe}
#
# These logs can be quite verbose and will contain the account key. Therefore, boto debug logs
# will be written only when the '-D' aminate option is passed and if boto_logdir is set with
# an existing directory.
boto_log_dir:
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
                    sys.stderr.write("{0}: {1}: line{2}, column{3}".format(e,
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
