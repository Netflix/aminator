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
import sys
from copy import deepcopy
from datetime import datetime

try:
    from logging.config import dictConfig
except ImportError:
    # py26
    from logutils.dictconfig import dictConfig

import bunch
from pkg_resources import resource_string, resource_exists

try:
    from yaml import CLoader as Loader
except ImportError:
    from yaml import Loader

import aminator


__all__ = ()
log = logging.getLogger(__name__)
_action_registries = argparse.ArgumentParser()._registries['action']

RSRC_PKG = 'aminator'
RSRC_DEFAULT_CONF_DIR = 'default_conf'
RSRC_DEFAULT_CONFS = {
    'main': os.path.join(RSRC_DEFAULT_CONF_DIR, 'aminator.yml'),
    'logging': os.path.join(RSRC_DEFAULT_CONF_DIR, 'logging.yml'),
    'environments': os.path.join(RSRC_DEFAULT_CONF_DIR, 'environments.yml'),
}


def init_defaults(argv=None):
    argv = argv or sys.argv[:]
    config = Config.from_defaults()
    config = config.dict_merge(config, Config.from_files(config.config_files.main))
    parser = Argparser(argv=argv, config=config)
    config.logging = LoggingConfig.from_defaults()
    config.logging = config.dict_merge(config.logging,
                                       LoggingConfig.from_files(config.config_files.logging))
    LoggingConfig.format_handler_filenames(config)
    config.environments = EnvironmentConfig.from_defaults()
    config.environments = config.dict_merge(config.environments,
                                            EnvironmentConfig.from_files(config.config_files.environments))
    dictConfig(config.logging.toDict())
    log.info('Aminator {0} default configuration loaded'.format(aminator.__version__))
    return config, parser


class Config(bunch.Bunch):
    """ Base config class """
    resource_package = RSRC_PKG
    resource_default = RSRC_DEFAULT_CONFS['main']

    @classmethod
    def from_yaml(cls, yaml_data, Loader=Loader):
        return cls(cls.fromYAML(yaml_data, Loader=Loader))

    @classmethod
    def from_pkg_resource(cls, namespace, name):
        config = resource_string(namespace, name)
        if len(config):
            return cls.from_yaml(config, Loader=Loader)
        else:
            log.warn('Resource for {0}.{1} is empty, returning empty config'.format(namespace, name))

    @classmethod
    def from_file(cls, yaml_file, Loader=Loader):
        if not os.path.exists(yaml_file):
            log.warn('File {0} not found, returning empty config'.format(yaml_file))
            return cls()
        with open(yaml_file) as f:
            _config = cls.from_yaml(f, Loader=Loader)
        return _config

    @classmethod
    def from_files(cls, files, Loader=Loader):
        _files = [os.path.expanduser(filename) for filename in files]
        _files = [filename for filename in _files if os.path.exists(filename)]
        _config = cls()
        for filename in _files:
            _new = cls.from_file(filename, Loader=Loader)
            _config = cls.dict_merge(_config, _new)
        return _config

    @classmethod
    def from_defaults(cls, namespace=None, name=None, Loader=Loader):
        if (namespace and name and resource_exists(namespace, name)):
            _namespace = namespace
            _name = name
        elif (cls.resource_package and cls.resource_default
              and resource_exists(cls.resource_package, cls.resource_default)):
            _namespace = cls.resource_package
            _name = cls.resource_default
        else:
            log.warn('No class resource attributes and no namespace info, returning empty config')
            return cls()
        return cls.from_pkg_resource(_namespace, _name)

    @staticmethod
    def dict_merge(old, new):
        res = deepcopy(old)
        for k, v in new.iteritems():
            if k in res and isinstance(res[k], dict):
                res[k] = Config.dict_merge(res[k], v)
            else:
                res[k] = deepcopy(v)
        return res

    def __call__(self):
        return self


class LoggingConfig(Config):
    """ Logging config class """
    resource_default = RSRC_DEFAULT_CONFS['logging']

    @staticmethod
    def format_handler_filenames(config):
        if 'handlers' in config.logging:
            for name, handler in config.logging.handlers.iteritems():
                if 'filename_format' not in handler:
                    continue
                context = {'package': config.package, 'now': datetime.utcnow()}
                handler.filename = handler.filename_format.format(context)
                del handler['filename_format']


class EnvironmentConfig(Config):
    """ Environment config class """
    resource_default = RSRC_DEFAULT_CONFS['environments']


class PluginConfig(Config):
    """ Plugin config class """
    resource_package = resource_default = None

    @classmethod
    def from_defaults(cls, namespace, name, Loader=Loader):
        resource_file = '.'.join((namespace, name, 'yml'))
        resource_path = os.path.join(RSRC_DEFAULT_CONF_DIR, resource_file)
        return super(PluginConfig, cls).from_defaults(namespace=namespace, name=resource_path,
                                                      Loader=Loader)


class Argparser(object):
    """ Argument parser class. Holds the keys to argparse """
    def __init__(self, argv=None, config=None, *args, **kwargs):
        log.debug('Initializing argparser')
        self._argv = argv or sys.argv[:]
        log.debug('argv: {0}'.format(self._argv))
        self._config = config or Config()
        self._parser = argparse.ArgumentParser(argument_default=argparse.SUPPRESS, *args, **kwargs)
        self._groups = {
            'main': self._parser,
            'required': self._parser.add_argument_group('required'),
        }
        self._add_immediate_arguments()

    def add_argument(self, *args, **kwargs):
        group = kwargs.pop('group', 'main')
        parse_immediate = kwargs.pop('parse_immediate', False)
        log.debug('adding argument group={0} parse_immediate={1} args={2} kwargs={3}'
                  .format(group, parse_immediate, args, kwargs))
        parser = self._groups[group]
        _arg = parser.add_argument(*args, **kwargs)
        if parse_immediate:
            log.debug('Parsing {0} from {1} immediately'.format(_arg, self._argv))
            _, self._argv = self._parser.parse_known_args(self._argv)

    def _add_immediate_arguments(self):
        self.add_argument('-p', '--package', dest='package', group='required',
                          parse_immediate=True, required=True, action=conf_action(self._config),
                          help='The package to aminate')


def conf_action(config, action=None):
    """
    class factory function that dynamically creates special ConfigAction
    forms of argparse actions, injecting a config object into the namespace
    """
    action_subclass = _action_registries[action]
    action_class_name = 'ConfigAction_{0}'.format(action_subclass.__name__)

    def _action_call(self, parser, namespace, values, option_string=None):
        return super(self.__class__, self).__call__(parser, config, values, option_string)

    action_class = type(action_class_name, (action_subclass, ), {'__call__': _action_call})
    return action_class
