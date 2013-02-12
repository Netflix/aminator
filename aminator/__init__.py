"""
Created by mtripoli on 2012-07-06.
Copyright (c) 2012 Netflix, Inc. All rights reserved.
"""

import logging

log = logging.getLogger(__name__)

try:
    from logging import NullHandler
except ImportError:
    class NullHandler(logging.Handler):
        def emit(self, record):
            pass

log.addHandler(NullHandler())
