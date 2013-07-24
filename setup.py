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

import sys
major, minor = sys.version_info[0:2]
if major != 2 or minor < 6:
    print 'Aminator requires Python 2.6.x or 2.7.x'
    sys.exit(1)

from distribute_setup import use_setuptools
use_setuptools()
from setuptools import setup, find_packages

import aminator

with open('requirements.txt') as fh:
    requires = [requirement.strip() for requirement in fh]

entry_points = {
    'console_scripts': [
        'aminate = aminator.cli:run',
    ],
    'aminator.plugins.cloud': [
        'ec2 = aminator.plugins.cloud.ec2:EC2CloudPlugin',
        'euca = aminator.plugins.cloud.euca:EucaCloudPlugin',
    ],
    'aminator.plugins.provisioner': [
        'yum = aminator.plugins.provisioner.yum:YumProvisionerPlugin',
        'apt = aminator.plugins.provisioner.apt:AptProvisionerPlugin',
        'apt_chef = aminator.plugins.provisioner.apt_chef:AptChefProvisionerPlugin',
        'apt_script = aminator.plugins.provisioner.apt_script:AptScriptProvisionerPlugin',
    ],
    'aminator.plugins.volume': [
        'linux = aminator.plugins.volume.linux:LinuxVolumePlugin',
        'virtio = aminator.plugins.volume.virtio:VirtioVolumePlugin',
    ],
    'aminator.plugins.blockdevice': [
        'linux = aminator.plugins.blockdevice.linux:LinuxBlockDevicePlugin',
        'virtio = aminator.plugins.blockdevice.virtio:VirtioBlockDevicePlugin',
    ],
    'aminator.plugins.finalizer': [
        'tagging_ebs = aminator.plugins.finalizer.tagging_ebs:TaggingEBSFinalizerPlugin',
        'tagging_ebs_euca = aminator.plugins.finalizer.tagging_ebs_euca:TaggingEBSEucaFinalizerPlugin',
    ],
}

exclude_packages = [
    'tests',
    'tests.*',
]

package_data = {'': ['default_conf/*.yml']}

# py2.6 compatibility
try:
    import argparse
except ImportError:
    requires.append('argparse')

try:
    from collections import OrderedDict
except ImportError:
    requires.append('ordereddict')

setup(
    name='aminator',
    version=aminator.__version__,
    description='Aminator: Bring an AMI to life',
    author='Netflix Engineering Tools',
    author_email='talent@netflix.com',
    url='https://github.com/netflix/aminator',
    packages=find_packages(exclude=exclude_packages),
    package_data=package_data,
    package_dir={'aminator': 'aminator'},
    include_package_data=True,
    zip_safe=False,
    install_requires=requires,
    entry_points=entry_points,
    license='ASL 2.0',
    classifiers=(
        'Development Status :: 4 - Beta',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'Intended Audience :: Information Technology',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: Apache Software License',
        'Natural Language :: English',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Topic :: System :: Installation/Setup',
        'Topic :: Utilities',
    ),
)
