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


def timer(metric_name, context_obj=None):
    def func_1(func):
        def func_2(obj, *args, **kwargs):
            start = time()
            try:
                retval = func(obj, *args, **kwargs)
                (context_obj or obj)._config.metrics.timer(metric_name, time() - start)
            except:
                (context_obj or obj)._config.metrics.timer(metric_name, time() - start)
                raise
            return retval
        return func_2
    return func_1


def lapse(metric_name, context_obj=None):
    def func_1(func):
        def func_2(obj, *args, **kwargs):
            (context_obj or obj)._config.metrics.start_timer(metric_name)
            try:
                retval = func(obj, *args, **kwargs)
                (context_obj or obj)._config.metrics.stop_timer(metric_name)
            except:
                (context_obj or obj)._config.metrics.stop_timer(metric_name)
                raise
            return retval
        return func_2
    return func_1


def fails(metric_name, context_obj=None):
    def func_1(func):
        def func_2(obj, *args, **kwargs):
            try:
                retval = func(obj, *args, **kwargs)
            except:
                (context_obj or obj)._config.metrics.increment(metric_name)
                raise
            if not retval:
                (context_obj or obj)._config.metrics.increment(metric_name)
            return retval
        return func_2
    return func_1


def cmdfails(metric_name, context_obj=None):
    def func_1(func):
        def func_2(obj, *args, **kwargs):
            try:
                retval = func(obj, *args, **kwargs)
            except:
                (context_obj or obj)._config.metrics.increment(metric_name)
                raise
            if not retval or not retval.success:
                (context_obj or obj)._config.metrics.increment(metric_name)
            return retval
        return func_2
    return func_1


def cmdsucceeds(metric_name, context_obj=None):
    def func_1(func):
        def func_2(obj, *args, **kwargs):
            retval = func(obj, *args, **kwargs)
            if retval and retval.success:
                (context_obj or obj)._config.metrics.increment(metric_name)
            return retval
        return func_2
    return func_1


def succeeds(metric_name, context_obj=None):
    def func_1(func):
        def func_2(obj, *args, **kwargs):
            retval = func(obj, *args, **kwargs)
            if retval:
                (context_obj or obj)._config.metrics.increment(metric_name)
            return retval
        return func_2
    return func_1


def raises(metric_name, context_obj=None):
    def func_1(func):
        def func_2(obj, *args, **kwargs):
            try:
                return func(obj, *args, **kwargs)
            except:
                (context_obj or obj)._config.metrics.increment(metric_name)
                raise
        return func_2
    return func_1
