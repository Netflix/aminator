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
#echo $BASH_SOURCE
#echo ${BASE_SOURCE/-/-redhat-}

install_updates(){
#
# Update packages in the base AMI.
# The list of packages is configured through aminator user data by
# setting the "PKG_updates" parameter in /etc/sysconfig/app-ami
#
# This list generally contains the monitoring packages.
#
    local mnt="$1"
    local yum="yum"
    local ret=0
    test -z "$mnt" && Log "$FUNCNAME <mnt>: null mnt." && return 1
    ! test -d "$mnt" && Log "$FUNCNAME: $mnt: directory does not exist." && return 1

    if [[ -n $PKG_updates ]]
    then
        short_circuit ${mnt}/sbin/service || return 1
        if ! wrap_log chroot $mnt $yum -e 1 -d 1 install -y $PKG_updates
        then
            ret=$?
            Log "package updates ($PKG_updates) failed."
        fi
        rewire ${mnt}/sbin/service
    fi

    return $ret
}


install_pkg(){
    local mnt=$1
    local rpmfile=$2

    ! [[ -f $rpmfile ]] && Log "$rpmfile: does not exist." && return 1

    short_circuit ${mnt}/sbin/service || return 1

    retry provision $rpmfile $mnt || return 1

    rewire ${mnt}/sbin/service || return 1

    return 0
}


provision(){
    local rpmfile=$1
    local mnt=$2
    

    if ! wrap_log chroot $mnt yum clean metadata
    then
        Log "${FUNCNAME}: clean metadata failed."
    fi

    yumcmd="localinstall -y ${rpmfile#$mnt}"
    if ! wrap_log chroot ${mnt} yum --nogpgcheck $yumcmd
    then
        Log "${FUNCNAME}: yum $yumcmd failed."
        return 1
    fi
    return 0
}


short_circuit(){
    local arg="$1"
    local ext="short-circuit"
    local true="/bin/true"
    # short-circuit /sbin/service so that services are not accidentally
    # started in the chroot'd environment which wreaks havoc for umount
    if ! wrap_log mv -v ${arg} ${arg}.${ext}
    then
        Log "${FUNCNAME}: short-circuiting $arg failed."
        return 1
    fi
    if ! wrap_log ln -v -s $true ${arg}
    then
        Log "${FUNCNAME}: link  $arg to $true failed."
        return 1
    fi
    return 0
}


rewire(){
    local arg="$1"
    local ext="short-circuit"

    wrap_log rm -f -v ${mnt}/sbin/service

    if ! wrap_log mv -v ${arg}.${ext} $arg
    then
        Log "${FUNCNAME}: restoring $arg failed."
        return 1
    fi
    return 0
}


configure_services(){
    local mnt="$1"
    # make sure services are enabled/disabled
    for svc in $enable_svcs
    do
        chroot $mnt /sbin/chkconfig $svc on
    done

    for svc in $disable_svcs
    do
        chroot $mnt /sbin/chkconfig $svc off
    done

    return 0
}
