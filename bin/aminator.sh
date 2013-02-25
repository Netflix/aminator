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

inc_d=${0%/*}
prog=${0##*/}
inc_f=${inc_d}/${prog%.sh}-funcs.sh

if [[ ! -f $inc_f ]]
then
    echo "$inc_f not found." >&2
    exit 1
fi

source $inc_f

parse_args "$@"

logging_init


case $action in
    install)
        inc_f=${inc_f/-/-$(distro_guess $action_args)-}
        if [[ -f $inc_f ]]
        then
            source $inc_f
        fi
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
