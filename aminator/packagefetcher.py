#!/usr/bin/env python2.7
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
import urllib2
import json
import logging
import os
import re
import shutil
import time
import boto.utils
from aminator import NullHandler

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)
log.addHandler(NullHandler())

rpm_attrs = (name, ver, rel, desc) = ('Name', 'Version', 'Release', 'Description')
bld_attrs = (job, num) = ('Build-Job', 'Build-Number')
mirror_re = '^http://'
mirror_pattern = re.compile(mirror_re)


class PackageFetchError(StandardError):
    """
    General PackageFetch error
    """
    def __init__(self, reason, **kwargs):
        StandardError.__init__(self, reason)
        self.reason = reason

    def __repr__(self):
        return 'PackageFetchError: %s' % self.reason

    def __str__(self):
        return 'PackageFetchError: %s' % self.reason


class PackageFetcher(object):
    def __init__(self, pkg=None):
        if pkg is None:
            raise PackageFetchError('pkg is None')
        self.repos = []
        with open('/etc/yum.repos.d/nflx.mirrors') as mirrors:
            for mirror in mirrors:
                if mirror_pattern.search(mirror):
                    self.repos.append(mirror.replace('$basearch', '').strip('\n'))
        log.info('looking up %s from:\n%s' % (pkg, '\n'.join(self.repos)))
        req = urllib2.urlopen(self._random_mirror('api/list.json?pkg=%s' % pkg))
        if req.code != 200:
            raise PackageFetchError('package %s not found [%d]' % (pkg, req.code))
        self.pkg_info = json.loads(req.read())
        self.pkg_info['pkg_uri'] = self.pkg_info['pkg_uri'].replace('ec2/', '')
        log.debug('download URI: %s' % (self.pkg_info['pkg_uri']))
        self.rpmfile = os.path.basename(self.pkg_info['pkg_uri'])
        self._rpminfo = {}

    def fetch(self, dst):
        """dowload rpm file to dst
        """
        if dst is None:
            raise PackageFetchError('Package destination is None.')
        if os.path.isdir(dst):
            self.rpmfilepath = os.path.join(dst, self.rpmfile)
        else:
            self.rpmfilepath = dst
        log.debug('downloading %s' % self.pkg_info['pkg_uri'])
        req = urllib2.urlopen(self._random_mirror(self.pkg_info['pkg_uri']))
        if req.code != 200:
            raise PackageFetchError('package %s not found [%d]' % (pkg, req.code))
        with open(self.rpmfilepath, 'w') as fp:
            shutil.copyfileobj(req.fp, fp)
        self._set_rpminfo()
        log.debug('%s: download complete.' % self.rpmfilepath)

    def _setReadOnly(self):
        raise AttributeError

    def _appversion(self):
        """return appversion string of the package
        """
        ret = ""
        if name not in self._rpminfo:
            return ret
        ret = self._rpminfo[name]
        if ver not in self._rpminfo:
            return ret
        ret = "%s-%s" % (ret, self._rpminfo[ver])
        if rel not in self._rpminfo:
            return ret
        ret = "%s-%s" % (ret, self._rpminfo[rel])
        if job not in self._rpminfo:
            return ret
        ret = "%s/%s" % (ret, self._rpminfo[job])
        if num not in self._rpminfo:
            return ret
        ret = "%s/%s" % (ret, self._rpminfo[num])
        return ret

    appversion = property(_appversion, _setReadOnly, None, 'name-version-release/build-name/build-num')

    def _name_ver_rel(self):
        """convenience method returning the name-version-release
           of the downloaded package.
        """
        return self.appversion.split('/')[0]

    name_ver_rel = property(_name_ver_rel, _setReadOnly, None, 'name-version-release')

    def _random_mirror(self, uri):
        if uri is None:
            uri = ""
        return(self.repos[int(time.time()) % len(self.repos)] + uri)

    def _set_rpminfo(self):
        # exectute the following command, parse the output, and store the info in self._rpminfo dict.
        # rpm -q --qf 'Name: %{N}\nVersion: %{V}\nRelease: %{R}\nDescritpion: %{DESCRIPTION} -p' self.rpmfilepath
        #
        cmd = ['rpm', '-q', '--qf']
        cmd.append('"%s: %%{N}\n%s: %%{V}\n%s: %%{R}\n%s: %%{DESCRIPTION}\n" -p ' % rpm_attrs)
        cmd.append(self.rpmfilepath)
        space = " "
        cmd = boto.utils.ShellCommand(space.join(cmd))
        key = ""
        for line in cmd.output.split('\n'):
            line_segs = line.split(':', 1)
            if len(line_segs) == 2:
                key = line_segs[0].strip()
                self._rpminfo[key] = line_segs[1].strip()
            else:
                # append to the previous key
                self._rpminfo[key] = self._rpminfo[key] + line_segs[0].strip() + "\n"


if __name__ == '__main__':
    log.addHandler(logging.StreamHandler())
    log.setLevel(logging.DEBUG)
    try:
        pkg = sys.argv[1]
    except IndexError:
        pkg = 'helloworld'
    p = PackageFetcher(pkg)
    p.fetch('/tmp')
    log.info(p.appversion)
    log.info(p.name_ver_rel)
