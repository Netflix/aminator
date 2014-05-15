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
aminator.plugins.metrics.logger
=============================
basic logger metrics collector
"""
import logging
from time import time

from aminator.plugins.metrics.base import BaseMetricsPlugin

__all__ = ('LoggerMetricsPlugin',)
log = logging.getLogger(__name__)


class LoggerMetricsPlugin(BaseMetricsPlugin):
    _name = 'logger'

    def __init__(self):
        super(LoggerMetricsPlugin,self).__init__()
        self.timers = {}

    def increment(self, name, value=1):
        log.info("Metric {}: increment {}, tags: {}".format(name,value, self.tags))

    def gauge(self, name, value):
        log.info("Metric {}: gauge set {}, tags: {}".format(name, value, self.tags))

    def timer(self, name, seconds):
        log.info("Metric {}: timer {}s, tags: {}".format(name, seconds, self.tags)) 

    def start_timer(self, name):
        log.info("Metric {}: start timer, tags: {}".format(name, self.tags))
        self.timers[name] = time()

    def stop_timer(self, name):
        log.info("Metric {}: stop timer [{}s], tags: {}".format(name, time() - self.timers[name], self.tags))
        del self.timers[name]
    
    def flush(self):
        for name in self.timers:
            log.warn("Metric {}: timer never stopped, started at {}, tags: {}".format(name, self.timers[name], self.tags))
