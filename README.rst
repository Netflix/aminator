aminator - Easily create application-specific custom AMIs
=========================================

Aminator creates a custom AMI from just:

* A base ami ID
* A link to a deb or rpm package that installs your application.

This is useful for many AWS workflows, particularly ones that take advantage of auto-scaling groups.

Requirements
------------

* Python 2.7 (Python 3.x support not yet available)
* Linux or UNIX cloud instance (EC2 currently supported)

Installation
------------
Clone this repository and run:

.. code-block:: bash

    # python setup.py install

*or*

.. code-block:: bash

    # pip install git+https://github.com/Netflix/aminator.git#egg=aminator

Usage
-----
::

    usage: aminate [-h] [-e ENVIRONMENT] [--version] [--debug] [-n NAME]
                   [-s SUFFIX] [-c CREATOR] (-b BASE_AMI_NAME | -B BASE_AMI_ID)
                   [--ec2-region REGION] [--boto-secure] [--boto-debug]
                   package

    positional arguments:
      package               package to aminate. A string resolvable by the native
                            package manager or a file system path or http url to
                            the package file.

    optional arguments:
      -h, --help            show this help message and exit
      -e ENVIRONMENT, --environment ENVIRONMENT
                            The environment configuration for amination
      --version             show program's version number and exit
      --debug               Verbose debugging output

    AMI Tagging and Naming:
      Tagging and naming options for the resultant AMI

      -n NAME, --name NAME  name of resultant AMI (default package_name-version-
                            release-arch-yyyymmddHHMM-ebs
      -s SUFFIX, --suffix SUFFIX
                            suffix of ami name, (default yyyymmddHHMM)
      -c CREATOR, --creator CREATOR
                            The user who is aminating. The resultant AMI will
                            receive a creator tag w/ this user

    Base AMI:
      EITHER AMI id OR name, not both!

      -b BASE_AMI_NAME, --base-ami-name BASE_AMI_NAME
                            The name of the base AMI used in provisioning
      -B BASE_AMI_ID, --base-ami-id BASE_AMI_ID
                            The id of the base AMI used in provisioning

    EC2 Options:
      EC2 Connection Information

      --ec2-region REGION   EC2 region (default: us-east-1)
      --boto-secure         Connect via https
      --boto-debug          Boto debug output

Details
-------
The rough amination workflow:

#. Create a volume from the snapshot of the base AMI
#. Attach and mount the volume
#. Chroot into mounted volume
#. Provision application onto mounted volume using rpm or deb package
#. Unmount the volume and create a snapshot
#. Register the snapshot as an AMI

Support
-------
* `Aminator Google Group <http://groups.google.com/group/Aminator>`_

Documentation
-------------
See the `aminator wiki <https://github.com/Netflix/aminator/wiki>`_ for documentation


License
-------
Copyright 2013 Netflix, Inc.

Licensed under the Apache License, Version 2.0 (the “License”); you may not use this file except in compliance with the License. You may obtain a copy of the License at
http://www.apache.org/licenses/LICENSE-2.0 Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on an “AS IS” BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the specific language governing permissions and limitations under the License.
