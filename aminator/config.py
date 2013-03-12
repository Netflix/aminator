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
aminator.config
===============
aminator configuration, argument handling, and logging setup
"""
import argparse
import logging
import os
import os.path
from datetime import datetime

import bunch
try:
    from yaml import CLoader as Loader
except ImportError:
    from yaml import Loader

import aminator


log = logging.getLogger(__name__)


class Config(bunch.Bunch):
    @staticmethod
    def from_yaml_file(yaml_file, Loader=Loader):
        log.debug('Reading {0} and bunchifying'.format(yaml_file))
        with open(yaml_file) as f:
            return Config.fromYAML(f, Loader=Loader)

    def apply_additional_configs(self):
        if 'additional_config_files' in self:
            while self.additional_config_files:
                config_file = self.additional_config_files.pop()
                if os.path.exists(config_file):
                    self.update(self.from_yaml_file(config_file))
                    self.config_files.append(config_file)

    def __call__(self):
        """
        this allows us to pass in an initialized configuration to aminator
        or just pass in the class name
        """
        return self


def config():
    _config = Config()
    log.debug('Loading default configuration')
    _config.update(_config.fromYAML(__doc__, Loader=Loader))
    log.debug('Applying external configuration')
    if 'config_files' in _config:
        for config_file in _config.config_files:
            if os.path.exists(config_file):
                log.debug('Applying configuration from {0}'.format(config_file))
                _config.update(_config.from_yaml_file(config_file))
    return _config


def config_action(config_root, action=None):
    """
    We want a part of our configuration bunch to be used in place of argparse
    namespaces. Rather than allow for a single type of action against a
    namespace (say, by subclassing argparse.Action), we sneak a peek at the action
    registry in an ArgumentParser instance.
    Our wrapper function takes the config root and an optional action (argparse
    maps the same action for None and 'store'). We pull out the right argparse
    action class, build a dummy __call__ method that calls super().__call__ with our
    namespace stuffed into the parameters, create a subclass of the right action
    class using type(), ensuring we map __call__ to our dummy call method in the dict.

    ...The Aristocrats!
    """
    _ = argparse.ArgumentParser()
    actions = _._registries['action']
    action_class = actions[action]

    def _action_call(self, parser, namespace, values, option_string=None):
        return super(self.__class__, self).__call__(parser, config_root, values, option_string)

    ConfigAction = type('ConfigAction', (action_class, ), {'__call__': _action_call})
    return ConfigAction


def argparsers(config):
    """
    Mainly for the CLI. Returns a dict of parsers. Plugins can twiddle the main parser
    or add their own
    """
    argparser = {}
    argparser['main'] = argparse.ArgumentParser(argument_default=argparse.SUPPRESS)
    argparser['mandatory'] = argparser['main'].add_argument_group('mandatory arguments')

    version = '%(prog)s {0}'.format(aminator.__version__)
    argparser['main'].add_argument('--version', action='version', version=version)

    config_help = 'The path to an additional config. May be specified multiple times (processed in order)'
    argparser['main'].add_argument('--config', dest='additional_config_files',
                                   action=config_action(config, 'append'), help=config_help)

    env_choices = config.environments.keys()
    argparser['main'].add_argument('-e', '--environment', choices=env_choices, )

    package_help = 'The name of (or in some cases, path to the package to aminate'
    argparser['mandatory'].add_argument('package', action=config_action(config), help=package_help)

    argparser['main'].parse_known_args()
    config.apply_additional_configs()
    return argparser


def init_logging(config):
    """
    Pulls in something akin to a dictConfig, but not as cool
    """
    if not os.path.exists(config.logging.dir):
        if config.logging.dir_create:
            os.mkdir(config.logging.dir)
        else:
            log.warn('Log dir {0} does not exist, log_dir_create is False'
                     .format(config.logging.dir))

    formatters = {}
    format_config = config.logging.formatters
    for formatter in format_config:
        klass = format_config[formatter]['class']
        format = format_config[formatter].format
        time_format = format_config[formatter].time_format
        formatters[formatter] = klass(format, time_format)

    handlers = {}
    handler_config = config.logging.handlers
    for handler in handler_config:
        klass = handler_config[handler]['class']
        formatter = formatters[handler_config[handler].formatter]
        level = handler_config[handler].level
        if 'stream' in handler_config[handler]:
            handlers[handler] = klass(handler_config[handler].stream)
        elif any(param in handler_config[handler]
                 for param in ('filename', 'filename_from_package')):
            if 'filename' in handler_config[handler]:
                filename = os.path.join(config.logging.dir,
                                        handler_config[handler].filename)

            elif 'filename_from_package' in handler_config[handler]:
                package = config.package
                filename = '{0}-{1:%Y%m%d%H%M}'.format(package, datetime.utcnow())
                filename = os.path.join(config.logging.dir, filename)
            handlers[handler] = klass(filename)
            handlers[handler].setLevel(level)
            handlers[handler].setFormatter(formatter)

    logger_config = config.logging.loggers
    for logger in logger_config:
        level = logger_config[logger].level
        for handler in logger_config[logger].handlers:
            logging.getLogger(logger).addHandler(handler)


__doc__ = """
# aminator default configuration settings
# This document is processed by yaml and formatted per
# http://pyyaml.org/wiki/PyYAMLDocumentation#Documents

# defaults can be overridden in these yaml files
config_files:
    - /etc/aminator.yaml
    - ~/.aminator.yaml

# lock file directory
lockdir: /var/lock

# volumes mounted onto subdirs of this directory.
volume_root: /aminator/volumes

# root_only: must Aminator run as root?
root_only: True

# some day this might become a dictConfig...
logging:
    dir: /var/log/aminator
    dir_create: True
    url_prefix:

    formatters:
        simple:
            class: logging.Formatter
            time_format: '%F %T'
            format: '%(asctime)s [%(levelname)s] %(message)s'
        detail:
            class: logging.Formatter
            time_format: '%F %T'
            format: '%(asctime)s [%(levelname)s] [%(filename)s(%(lineno)s):%(funcName)s] %(message)s'
    handlers:
        console:
            class: logging.StreamHandler
            stream: sys.stdout
            formatter: simple
            level: logging.INFO
        logfile:
            class: logging.FileHandler
            formatter: detail
            level: logging.DEBUG
            filename_from_config: package
            filename_format: '{0}-{1:%Y%m%d%H%M}'
    loggers:
        aminator:
            level: logging.DEBUG
            handlers: [console, logfile]
        root:
            level: logging.DEBUG
            handlers: []

# plugins: plugin configuration
plugins:
    # plugin_paths: Directory where one can install plugin modules
    plugin_paths: /usr/share/aminator/plugins
    cloud:
        ec2:
            enabled: true
            root_device: /dev/sda1
            ephemeral_devices:
                - /dev/sdb
                - /dev/sdc
                - /dev/sdd
                - /dev/sde
    provisioner:
        yum:
            enabled: true
            short_circuit_sbin_service: true
        apt:
            enabled: true
    volume_manager:
        linux:
            enabled: true
            chroot_mounts:
                # fstab-esque list of mounts for a chroot environment. ordered.
                # device, type, mount point
                - [proc, proc, /proc]
                - [sysfs, sysfs, /sys]
                - [/dev, bind, /dev]
                - [devpts, devpts, /dev/pts]
                - [binfmt_misc, binfmt_misc, /proc/sys/fs/binfmt_misc]
    device_manger:
        linux:
            enabled: true
            # possible OS device prefixes
            device_prefixes: [sd, xvd]
            # think device_prefix + device letter (sda, sdb, xvda, etc)
            device_letters: 'fghijklmnop'

# ties everything together
environment: ec2_yum_linux
# mix and match
environments:
    ec2_yum_linux:
        cloud: ec2
        provisioner: yum
        volume_allocator: linux
        device_allocator: linux
    ec2_apt_linux:
        cloud: ec2
        provisioner: apt
        volume_allocator: linux
        device_allocator: linux
"""
