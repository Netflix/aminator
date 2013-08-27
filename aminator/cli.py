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
aminator.cli
============
command-line entry
"""
import logging
import sys

from aminator.config import Argparser
from aminator.core import Aminator


__all__ = ('run',)
log = logging.getLogger(__name__)


def run():
    # we throw this one away, real parsing happens later
    # this is just for getting a debug flag for verbose logging.
    # to be extra sneaky, we add a --debug to the REAL parsers so it shows up in help
    # but we don't touch it there :P
    bootstrap_parser = Argparser(add_help=False)
    bootstrap_parser.add_argument('--debug', action='store_true')
    bootstrap_parser.add_argument('-e', "--environment", dest="env")
    args, argv = bootstrap_parser.parse_known_args()
    sys.argv = [sys.argv[0]] + argv
    # add -e argument back argv for when we parse the args again
    if args.env:
        sys.argv.extend(["-e",args.env])

    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig()
    sys.exit(Aminator(debug=args.debug, envname=args.env).aminate())
