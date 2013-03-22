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
aminator.util
=============
Utilities
"""
import functools
import logging
from time import sleep

from decorator import decorator


log = logging.getLogger(__name__)


def retry(ExceptionToCheck=None, tries=3, delay=0.5, backoff=1, logger=None):
    """
    Retries a function or method until it returns True.

    delay sets the initial delay in seconds, and backoff sets the factor by which
    the delay should lengthen after each failure. backoff must be greater than 1,
    or else it isn't really a backoff. tries must be at least 0, and delay
    greater than 0.
    http://wiki.python.org/moin/PythonDecoratorLibrary#Retry
    """
    if logger is None:
        logger = log

    @decorator
    def _retry(f, *args, **kwargs):
        _tries, _delay = tries, delay

        while _tries > 0:
            try:
                return f(*args, **kwargs)
            except ExceptionToCheck, e:
                logger.debug(e)
                sleep(_delay)
                _tries -= 1
                _delay *= backoff
        return f(*args, **kwargs)
    return _retry


def memoize(obj=None):
    """
    http://wiki.python.org/moin/PythonDecoratorLibrary#Alternate_memoize_as_nested_functions
    """
    cache = obj.cache = {}

    @functools.wraps(obj)
    def memoizer(*args, **kwargs):
        if args not in cache:
            cache[args] = obj(*args, **kwargs)
        return cache[args]
    return memoizer
