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
aminator.util.metrics
===================
Metrics utility functions
"""

from time import time

def timer(metric_name):
    def func_1(func):
        def func_2(self, *args, **kwargs):
            start = time()
            try:
                retval = getattr(self, func.__name__)(*args,**kwargs)
                self._config.metrics.timer(metric_name, time() - start)
            except:
                self._config.metrics.timer(metric_name, time() - start)
                raise
            return retval
        return func_2
    return func_1

def fails(metric_name):
    def func_1(func):
        def func_2(self, *args, **kwargs):
            try:
                retval = getattr(self, func.__name__)(*args,**kwargs)
            except:
                self._config.metrics.increment(metric_name)
                raise
            if not retval:
                self._config.metrics.increment(metric_name)
            return retval
        return func_2
    return func_1

def cmdfails(metric_name):
    def func_1(func):
        def func_2(self, *args, **kwargs):
            try:
                retval = getattr(self, func.__name__)(*args,**kwargs)
            except:
                self._config.metrics.increment(metric_name)
                raise
            if not retval or not retval.success:
                self._config.metrics.increment(metric_name)
            return retval
        return func_2
    return func_1

def cmdsucceeds(metric_name):
    def func_1(func):
        def func_2(self, *args, **kwargs):
            retval = getattr(self, func.__name__)(*args,**kwargs)
            if retval and retval.success:
                self._config.metrics.increment(metric_name)
            return retval
        return func_2
    return func_1

def succeeds(metric_name):
    def func_1(func):
        def func_2(self, *args, **kwargs):
            retval = getattr(self, func.__name__)(*args,**kwargs)
            if retval:
                self._config.metrics.increment(metric_name)
            return retval
        return func_2
    return func_1

def raises(metric_name):
    def func_1(func):
        def func_2(self, *args, **kwargs):
            try:
                return getattr(self, func.__name__)(*args,**kwargs)
            except:
                self._config.metrics.increment(metric_name)
                raise
        return func_2
    return func_1
    
