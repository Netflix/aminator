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

import aminator

from distribute_setup import use_setuptools
use_setuptools()

from setuptools import setup, find_packages

requires = [
    'boto>=2.7',
    'botocore>=0.4.2',
    'requests',
    'envoy'
]

scripts = [
    'bin/aminator.sh',
    'bin/aminator-funcs.sh',
]

entry_points = {
    'console_scripts': [
        'aminate = aminator.cli:run',
    ]
}

exclude_packages = [
    'tests',
    'tests.*',
]

# py2.6 compatibility
try:
    import argparse
except ImportError:
    requires.append('argparse')

setup(
    name='aminator',
    version=aminator.__version__,
    packages=find_packages(exclude=exclude_packages),
    scripts=scripts,
    install_requires=requires,
    entry_points=entry_points,
    license=open('LICENSE.TXT').read(),
)
