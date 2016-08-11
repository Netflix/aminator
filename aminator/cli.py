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
    import os
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
        sys.argv.extend(["-e", args.env])
        os.environ["AMINATOR_ENVIRONMENT"] = args.env

    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig()
    sys.exit(Aminator(debug=args.debug, envname=args.env).aminate())


def plugin_manager():
    import subprocess
    import requests
    import argparse
    import tempfile
    import tarfile
    import shutil
    import yaml
    import re
    import os

    from cStringIO import StringIO

    parser = argparse.ArgumentParser(description='Aminator plugin install utility')

    parser.add_argument('--branch', help='Which branch to pull the plugin list from. Valid options: production, testing, alpha. Default value: production', default='production', choices=['production', 'testing', 'alpha'], dest='branch', metavar='branch')
    parser.add_argument('--type', help='The type of plugin to search for. Valid options: cloud, volume, blockdevice, provision, distro, finalizer, metrics', choices=['cloud', 'volume', 'blockdevice', 'provision', 'distro', 'finalizer', 'metrics'], dest='type', metavar='plugin-type')
    parser.add_argument('command', help='Command to run. Valid commands: search install list', choices=['search', 'install', 'list'], metavar='command')
    parser.add_argument('name', help='Name of the plugin', metavar='name', nargs='?')
    args = parser.parse_args()

    req = requests.get('https://raw.github.com/aminator-plugins/metadata/%s/plugins.yml' % (args.branch))
    plugins = yaml.load(req.text)

    if args.command == 'search':
        if not args.name:
            print "ERROR: You must supply a keyword to search for"
            sys.exit()

        results = []
        rgx = re.compile(args.name, re.I)
        for name, data in plugins.items():
            m = rgx.search(name)
            if not m:
                for alias in data['aliases']:
                    m = rgx.search(alias)
                    if m:
                        break

            if m:
                if args.type and args.type != data['type']:
                    continue
                results.append("Name:        %s\nAliases:     %s\nType:        %s\nDescription: %s" % (name, ", ".join(data['aliases']), data['type'], data['description']))

        if len(results) == 0:
            print "No plugins found for keyword %s" % args.name
        else:
            print "\n----------\n".join(results)

    elif args.command == 'list':
        results = []
        for name, data in plugins.items():
            if args.type and args.type != data['type']:
                continue
            results.append("Name:        %s\nAliases:     %s\nType:        %s\nDescription: %s" % (name, ", ".join(data['aliases']), data['type'], data['description']))

        if len(results) == 0:
            print "No plugins found"
        else:
            print "\n----------\n".join(results)

    elif args.command == 'install':
        if not args.name:
            print "ERROR: You must supply a plugin name to install"
            sys.exit()

        if os.geteuid() != 0:
            print "ERROR: You must run installs as root (or through sudo)"
            sys.exit()

        rgx = re.compile('^%s$' % args.name, re.I)
        plugin = None

        for name, data in plugins.items():
            m = rgx.match(name)
            if not m:
                for alias in data['aliases']:
                    m = rgx.match(alias)
                    if m:
                        plugin = data
                        break
            else:
                plugin = data

        if not plugin:
            print "Unable to find a plugin named %s. You should use the search to find the correct name or alias for the plugin you want to install" % args.name
            sys.exit()
        else:
            url = 'https://github.com/aminator-plugins/%s/archive/%s.tar.gz' % (plugin['repo_name'], plugin['branch'])
            print "Downloading latest version of %s from %s" % (args.name, url)
            req = requests.get(url, stream=True)

            tar = tarfile.open(mode="r:*", fileobj=StringIO(req.raw.read()))

            tmpdir = tempfile.mkdtemp()
            tar.extractall(path=tmpdir)

            install_path = os.path.join(tmpdir, "%s-%s" % (plugin['repo_name'], plugin['branch']))
            exe = subprocess.Popen([sys.executable, 'setup.py', 'install'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=install_path)
            out, err = exe.communicate()
            if exe.returncode > 0:
                outf = open(os.path.join(tmpdir, "install.log"), 'w')
                outf.write(out)
                outf.close()

                errf = open(os.path.join(tmpdir, "install.err"), 'w')
                errf.write(err)
                errf.close()

                print "Plugin installation failed. You should look at install.log and install.err in the installation folder, %s, for the cause of the failure" % tmpdir
            else:
                print "%s plugin installed successfully, removing temp dir %s" % (args.name, tmpdir)
                shutil.rmtree(tmpdir)
