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
aminator
========
Create images from packages for deployment in various cloud formations
"""
import logging
try:
    from logging import NullHandler
except ImportError:
    # py26
    try:
        from logutils import NullHandler
    except ImportError:
        class NullHandler(logging.Handler):
            def emit(self, record):
                pass

__version__ = '1.2.138-dev'
__versioninfo__ = __version__.split('.')
__all__ = ()

logging.getLogger(__name__).addHandler(NullHandler())
