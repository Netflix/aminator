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
aminator.plugins.metrics.base
============================
Base class(es) for metrics plugins
"""
import abc
import logging

from aminator.plugins.base import BasePlugin


__all__ = ('BaseMetricsPlugin',)
log = logging.getLogger(__name__)


class BaseMetricsPlugin(BasePlugin):
    """
    """
    __metaclass__ = abc.ABCMeta
    _entry_point = 'aminator.plugins.metrics'

    @abc.abstractmethod
    def increment(self, name, value=1):
        pass

    @abc.abstractmethod
    def gauge(self, name, value):
        pass

    @abc.abstractmethod
    def timer(self, name, seconds):
        pass

    @abc.abstractmethod
    def start_timer(self, name):
        pass

    @abc.abstractmethod
    def stop_timer(self, name):
        pass

    @abc.abstractmethod
    def flush(self):
        pass

    def add_tag(self, name, value):
        self.tags[name] = value

    def __init__(self):
        super(BaseMetricsPlugin, self).__init__()
        self.tags = {}

    def __enter__(self):
        setattr(self._config, "metrics", self)
        return self

    def __exit__(self, exc_type, exc_value, trace):
        self.flush()
        if exc_type:
            log.debug('Exception encountered in metrics plugin context manager',
                      exc_info=(exc_type, exc_value, trace))
        return False
