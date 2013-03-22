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
aminator.exceptions
===================
aminator's exceptions
"""


class AminateException(Exception):
    """ Base Aminator Exception """
    pass


class DeviceException(AminateException):
    """ Errors during device allocation """
    pass


class VolumeException(AminateException):
    """ Errors during volume allocation """
    pass


class ArgumentError(AminateException):
    """ Errors during argument parsing"""


class ProvisionException(AminateException):
    """ Errors during provisioning """


class FinalizerException(AminateException):
    """ Errors during finalizing """
