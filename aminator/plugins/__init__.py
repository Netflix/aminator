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
aminator.plugins
================
plugin support for aminator

Aminator currently provides the following major plugin points:
- clouds (interfaces to cloud providers)
- device allocators (components that reserve and provide OS devices to volume managers)
- volume managers (components that attach cloud volumes and prepare them for amination)
- provisioners (components that deploy applications into the volumes provided by volume managers)
- finalizers (components that tag and register the resultant image)

Plugins may be discovered through setuptools/distribute's entry_points mechanism
or registered by placing modules on a configurable plugin path for discovery.
"""
