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

from aminator.util import randword
try:
    from logging.config import dictConfig
except ImportError:
    # py26
    from logutils.dictconfig import dictConfig

import bunch
from pkg_resources import resource_string, resource_exists

try:
    from yaml import CLoader as Loader  # pylint: disable=redefined-outer-name
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


def init_defaults(argv=None, debug=False):
    argv = argv or sys.argv[1:]
    config = Config.from_defaults()
    config = config.dict_merge(config, Config.from_files(config.config_files.main, config.config_root))
    main_parser = Argparser(argv=argv, description='Aminator: bringing AMIs to life', add_help=False, argument_default=argparse.SUPPRESS)
    config.logging = LoggingConfig.from_defaults()
    config.logging = config.dict_merge(config.logging, LoggingConfig.from_files(config.config_files.logging, config.config_root))
    config.environments = EnvironmentConfig.from_defaults()
    config.environments = config.dict_merge(config.environments, EnvironmentConfig.from_files(config.config_files.environments, config.config_root))
    default_metrics = getattr(config.environments, "metrics", "logger")
    for env in config.environments:
        if isinstance(config.environments[env], dict):
            if "metrics" not in config.environments[env]:
                config.environments[env]["metrics"] = default_metrics

    if config.logging.base.enabled:
        dictConfig(config.logging.base.config.toDict())
    if debug:
        logging.getLogger().setLevel(logging.DEBUG)
        for handler in logging.getLogger().handlers:
            handler.setLevel(logging.DEBUG)

    add_base_arguments(parser=main_parser, config=config)
    plugin_parser = Argparser(argv=argv, add_help=True, argument_default=argparse.SUPPRESS, parents=[main_parser])
    log.info('Aminator {0} default configuration loaded'.format(aminator.__version__))
    return config, plugin_parser


class Config(bunch.Bunch):
    """ Base config class """
    resource_package = RSRC_PKG
    resource_default = RSRC_DEFAULT_CONFS['main']

    @classmethod
    def from_yaml(cls, yaml_data, Loader=Loader, *args, **kwargs):  # pylint: disable=redefined-outer-name
        return cls(cls.fromYAML(yaml_data, Loader=Loader, *args, **kwargs))

    @classmethod
    def from_pkg_resource(cls, namespace, name, *args, **kwargs):
        config = resource_string(namespace, name)
        if len(config):
            return cls.from_yaml(config, *args, **kwargs)
        else:
            log.warn('Resource for {0}.{1} is empty, returning empty config'.format(namespace, name))

    @classmethod
    def from_file(cls, yaml_file, *args, **kwargs):
        if not os.path.exists(yaml_file):
            log.warn('File {0} not found, returning empty config'.format(yaml_file))
            return cls()
        with open(yaml_file) as f:
            _config = cls.from_yaml(f, *args, **kwargs)
        return _config

    @classmethod
    def from_files(cls, files, config_root="", *args, **kwargs):
        _files = [os.path.expanduser(filename) for filename in files]
        _files = [(x if x.startswith('/') else os.path.join(config_root, x)) for x in _files]
        _files = [filename for filename in _files if os.path.exists(filename)]
        _config = cls()
        for filename in _files:
            _new = cls.from_file(filename, *args, **kwargs)
            _config = cls.dict_merge(_config, _new)
        return _config

    @classmethod
    def from_defaults(cls, namespace=None, name=None, *args, **kwargs):
        if namespace and name and resource_exists(namespace, name):
            _namespace = namespace
            _name = name
        elif (cls.resource_package and cls.resource_default and resource_exists(cls.resource_package, cls.resource_default)):
            _namespace = cls.resource_package
            _name = cls.resource_default
        else:
            log.warn('No class resource attributes and no namespace info, returning empty config')
            return cls(*args, **kwargs)
        return cls.from_pkg_resource(_namespace, _name, *args, **kwargs)

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
        return


class LoggingConfig(Config):
    """ Logging config class """
    resource_default = RSRC_DEFAULT_CONFS['logging']


def configure_datetime_logfile(config, handler):
    try:
        filename_format = config.logging[handler]['filename_format']
    except KeyError:
        log.error('filename_format not configured for handler {0}'.format(handler))
        return

    try:
        pkg = "{0}-{1}".format(os.path.basename(config.context.package.arg), randword(6))
        filename = os.path.join(config.log_root, filename_format.format(pkg, datetime.utcnow()))
    except IndexError:
        errstr = 'Missing replacement fields in filename_format for handler {0}'.format(handler)
        log.error(errstr)
        log.debug(errstr, exc_info=True)

    # find handler amongst all the loggers and reassign the filename/stream
    for h in [x for l in logging.root.manager.loggerDict for x in logging.getLogger(l).handlers] + logging.root.handlers:
        if getattr(h, 'name', '') == handler:
            assert isinstance(h, logging.FileHandler)
            h.stream.close()
            h.baseFilename = filename
            h.stream = open(filename, 'a')
            url_template = config.logging[handler].get('web_log_url_template', False)
            if url_template:
                url_attrs = config.context.web_log.toDict()
                url_attrs['logfile'] = os.path.basename(filename)
                url = url_template.format(**url_attrs)
                log.info('Detailed {0} output to {1}'.format(handler, url))
            else:
                log.info('Detailed {0} output to {1}'.format(handler, filename))
            break
    else:
        log.error('{0} handler not found.'.format(handler))


class EnvironmentConfig(Config):
    """ Environment config class """
    resource_default = RSRC_DEFAULT_CONFS['environments']


class PluginConfig(Config):
    """ Plugin config class """
    resource_package = resource_default = None

    @classmethod
    def from_defaults(cls, namespace=None, name=None, *args, **kwargs):
        if not all((namespace, name)):
            raise ValueError('Plugins must specify a namespace and name')
        resource_file = '.'.join((namespace, name, 'yml'))
        resource_path = os.path.join(RSRC_DEFAULT_CONF_DIR, resource_file)
        return super(PluginConfig, cls).from_defaults(namespace=namespace, name=resource_path, *args, **kwargs)


class Argparser(object):
    """ Argument parser class. Holds the keys to argparse """

    def __init__(self, argv=None, *args, **kwargs):
        self._argv = argv or sys.argv[1:]
        self._parser = argparse.ArgumentParser(*args, **kwargs)

    def add_config_arg(self, *args, **kwargs):
        config = kwargs.pop('config', Config())
        _action = kwargs.pop('action', None)
        action = conf_action(config, _action)
        kwargs['action'] = action
        return self.add_argument(*args, **kwargs)

    def __getattr__(self, attr):
        return getattr(self._parser, attr)


def add_base_arguments(parser, config):
    parser.add_config_arg('arg', metavar='package_spec', config=config.context.package, help='package to aminate. A string resolvable by the native package manager or a file system path or http url to the package file.')
    parser.add_config_arg('-e', '--environment', config=config.context, help='The environment configuration for amination')
    parser.add_config_arg('--preserve-on-error', action='store_true', config=config.context, help='For Debugging. Preserve build chroot on error')
    parser.add_config_arg('--verify-https', action='store_true', config=config.context, help='Specify if one wishes for plugins to verify SSL certs when hitting https URLs')
    parser.add_argument('--version', action='version', version='%(prog)s {0}'.format(aminator.__version__))
    parser.add_argument('--debug', action='store_true', help='Verbose debugging output')


def conf_action(config, action=None):
    """
    class factory function that dynamically creates special ConfigAction
    forms of argparse actions, injecting a config object into the namespace
    """
    action_subclass = _action_registries[action]
    action_class_name = 'ConfigAction_{0}'.format(action_subclass.__name__)

    def _action_call(self, parser, namespace, values, option_string=None):
        return super(self.__class__, self).__call__(parser, config, values, option_string)

    action_class = type(action_class_name, (action_subclass,), {'__call__': _action_call})
    return action_class
