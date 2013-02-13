#!/bin/bash
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

inc=${0%/*}
prog=${0##*/}
. ${inc}/${prog%.sh}-funcs.sh

parse_args "$@"

case $action in
    mount)
    # mount volume
    # install updates
        mnt=$(mount_dev $action_args) || exit 1
        install_updates $mnt || exit 1
        configure_services $mnt || exit 1
        ;;
    unmount)
        umount_dev $action_args || exit 1
        ;;
    install)
        install_pkg $action_args || exit 1
        ;;
    *)
        err "unsupported action: $action"
        exit 1
        ;;
esac

if [[ -n $TMPFILES ]]
then
    wrap_log rm -f -v ${TMPFILES[*]}
fi
exit 0
