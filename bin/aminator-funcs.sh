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

PATH=/bin:/usr/bin:/usr/local/bin:/sbin:/usr/sbin:/etc/alternatives/jre/bin:/root/bin
prog=${prog:-$( [[ $0 != -bash ]] &&  ${0##*/})}

test -f /etc/sysconfig/app-ami && source /etc/sysconfig/app-ami

# directory for mount points for attached base AMI volumes.
oven=${oven:-"/aminator/oven"}

mkdir -p $oven

loglevel="local1.info"

parse_args(){
    while getopts 'a:t:x' OPTION
    do
        case $OPTION in
            # action
            a) action=${OPTARG} ;;
            # logging tag
            t) log_tag=${OPTARG} ;;
            x) set -x ;;
            *) echo "${OPTION}: unknown option." &&  exit 1 ;;
        esac
    done
    shift $(($OPTIND - 1))
    action_args="$@"
}

# Actions

mount_dev(){
#
# mounts device to $oven/$(basename $dev)
#
# Args:
#       dev=$1: device to mount
# rvalue:
#      0 - success
#      1 = failure
# stdout - n/a
# stderr - error message
    local dev="$1"
    local mnt="$2"
    local i resp ret
    let i=3
    while [[ ! -e $dev ]]
    do
        sleep 5
        (( i-- > 0 )) || break
    done

    if [[ ! -e $dev ]]
    then
        err "$dev doesn't exist."
        return 1
    fi

    mkdir -p $mnt

    for cmd in "e2fsck -pvtt $dev" "mount $dev $mnt" "configureChroot $mnt up"
    do
        wrap_log "$cmd"
        ret=$?
        if [[ $ret -ne 0 ]]
        then
            err "$cmd failed."
            return $ret
        fi
    done
    echo $mnt
    return 0
}


umount_dev(){
#
# unmounts device
#
# Args:
#       dev=$1: device to unmount
# rvalue:
#      0 - success
#      1 = failure
# stdout - n/a
# stderr - error message
    local dev="$1"
    local mnt=${oven}/${dev##*/}
    local t0=`date +%s`
    local out=""

    if ! mounted $mnt
    then
	return 0
    fi

    while lsof $mnt 2>> /dev/null
    do
        sleep 5
        if [[ $(( `date +%s` - $t0 )) -gt 120 ]]
	then
	    err"$mnt busy for too long, giving up."
	    return 1
	fi
    done

    for cmd in "configureChroot $mnt down" "umount $dev" "e2fsck -pvtt $dev"
    do
        wrap_log "$cmd"
        ret=$?
        if [[ $ret -ne 0 ]]
        then
    	    err "$cmd failed."
	    return $ret
        fi
    done

    echo "$dev unmounted."
    return 0
}


#
# supporting functions
#

mounted(){
    grep -q $1 /proc/mounts
}

add_to_fstab(){
    local dev=$1
    local mnt=$2

    grep -qE "$dev $mnt " /etc/fstab && return
    echo "$dev $mnt ext3 rw,data=ordered 0 0" >> /etc/fstab
}


configureChroot(){
# setup/teardown chroot environment relative to $root
#
# params: root="directory path"
#       action="up|down"
    local root="$1"
    local action="$2"
    local m=""

    for m in proc sys dev
    do
        M=${root}/${m}
        m=/${m}
        case $action in
            up) test -d $M || mkdir -p $m
                ! mount --bind $m $M && Log "mount $m failed." && return 1
                ;;
          down) for i in $( mounts $M )
                do
                    ! umount $i && Log "umount $i failed." && return 1
                done
                ;;
             *) Log "\"$action\": unkown action." && return 1
                ;;
        esac
    done
    return 0
}


mounts(){
# print mount points of $1 in reverse order of occurance in /proc/mounts
    perl -s -e '{
        undef $/;
        foreach ( reverse( split("\n", <>)) ){
            print $1, "\n" if ( m#^.*\s($d\S*)\s.*$# );
        }
    }' -- -d=${1} /proc/mounts
}


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
    local rpmfile=$1
    local mnt=$2

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


mktmpfile(){
    local tmp=$(mktemp -t ${prog}.XXXXXXXX) || return 1
    echo $tmp
}

wrap_log(){
# general purpose wrapper for logging the output of a command and
# returning the status of the command.
    local tmp=$(mktmpfile) || return 1
    TMPFILES=( ${TMPFILES[*]} $tmp )
    local cmd="$@"
    local ret

    exec 3> $tmp
    Log $cmd
    ( $cmd; echo "<exit_status>$?</exit_status>" >&3 ) 2>&1 | Log
    exec 3>&-

    [[ $(getStatus $tmp) == 0 ]]
}

getStatus(){
    perl -ne 'print $1 if( m/^<exit_status>(\d+)<\/exit_status>$/ )' $1
    perl -ne 'next if( m/^<exit_status>(\d+)<\/exit_status>$/ ); print;' -i $1
}


err() {
    echo "$@" 1>&2
}


Log() {
    # args or stdin
    LOGGERCMD="/bin/logger -t ${prog}[$$]:[${log_tag}] -p ${loglevel}"
    if [ $# -ne 0 ]
    then
        ${LOGGERCMD} -- "$*"
    else
        while read line; do
            # logger reads from stdin if given no positional message arg
            ${LOGGERCMD} -- "$line"
        done
    fi
}

retry () 
{ 
    cmd="$@";
    let tries=3;
    while true; do
        eval "$cmd";
        if [[ $? == 0 ]]; then
            return 0;
        else
            if (( --tries <= 0 )); then
                return 1;
            else
                echo "retrying $cmd $tries more times";
            fi;
        fi;
    done
}

