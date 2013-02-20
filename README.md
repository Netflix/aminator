## Description

AMInator -- A tool for creating EBS AMIs.
This tool currently works for CentOS/RedHat Linux images and is inteded to run on an EC2 instance.

## Requirements

* Python 2.6+ (Python 3.x support not yet available)
* Linux or UNIX cloud instance (EC2 currently supported)

## Installation

Clone this repository and run 

`python setup.py install`

*or*

`pip install git+https://github.com/Netflix/aminator.git#egg=aminator`

## Usage

```
Usage: aminate [options]

Options:
  -h, --help            show this help message and exit
  -b BASE_AMI_NAME      REQUIRED, the name of base AMI on which to build.
  -p PKG                REQUIRED, name of package to install
  -n NAME               name of resultant AMI (default package_name-version-
                        release-arch-yyyymmddHHMM-ebs)
  -r REGIONS, DEFAULT=NONE
                        comma delmitted list of regions to copy resultant AMI
                        (unimplemented)
  -s SUFFIX             suffix of ami name, (default yyyymmddHHMM)
  -c CREATOR            the name of the user invoking aminate, resultant AMI 
                        will receive a creator tag w/ this user
```
## Details

The rough amination workflow:

1. Create a volume from the snapshot of the base AMI
1. Attach and mount the volume
1. Chroot into mounted volume and provision application
1. Unmount the volume and create a snapshot
1. Register the snapshot as an AMI

## Documentation

See the AMInator wiki at https://github.com/Netflix/aminator/wiki


## License

Copyright 2013 Netflix, Inc.

Licensed under the Apache License, Version 2.0 (the “License”); you may not use this file except in compliance with the License. You may obtain a copy of the License at

http://www.apache.org/licenses/LICENSE-2.0 Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on an “AS IS” BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the specific language governing permissions and limitations under the License.
