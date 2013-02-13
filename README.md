AMInator -- A tool for creating EBS AMIs.

This tool currently works for CentOS/RedHat Linux images and is inteded to run on an EC2 instance.

<pre>
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
  -e EXECUTOR           the name of the user invoking
</pre>

How it Works
============

* Create volume from the snapshot of the base AMI.
* Attach and mount volume
* Install package into mounted volume.
* Create snapshot of volume.
* Register snapshot as an AMI.
