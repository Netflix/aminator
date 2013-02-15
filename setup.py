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
    'boto'
]

try:
    import argparse
except ImportError:
    requires.append('argparse')

setup(
    name='aminator',
    version=aminator.__version__,
    packages=find_packages(),
    scripts=["bin/aminator.sh", "bin/aminator-funcs.sh"],
    install_requires=requires,
    entry_points={
        'console_scripts': [
            'aminate = aminator.cli:run',
        ],
    },
    license=open('LICENSE.TXT').read(),
)
