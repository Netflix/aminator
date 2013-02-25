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
syslog_level="user.info"
extra_log_tag=""
log_to_syslog=false
LOGGERCMD=echo

parse_args(){
    while getopts 'a:l:st:x' OPTION
    do
        case $OPTION in
            # action
            a) action=${OPTARG} ;;
            l) syslog_level=${OPTARG} ;;
            s) log_to_syslog=true ;;
            # adt'l logging tag for, say, the pid of the caller
            t) extra_log_tag=${OPTARG} ;;
            x) set -x ;;
            *) echo "${OPTION}: unknown option." &&  exit 1 ;;
        esac
    done
    shift $(($OPTIND - 1))
    action_args="$@"
}


mktmpfile(){
    local tmp=$(mktemp -t ${prog}.XXXXXXXX) || return 1
    echo $tmp
}


wrap_log(){
# general purpose wrapper for logging the output of a command and
# returning the status of the command.
    local tmp=$(mktmpfile) || return 1
    local cmd="$@"
    local ret

    Log $cmd
    $cmd >> $tmp 2>&1
    ret=$?
    cat $tmp | Log
    rm -f $tmp
    [[ $ret == 0 ]]
}


err() {
    echo "$@" 1>&2
}


Log() {
    # args or stdin
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


distro_guess(){
    local mnt=$1
    [[ -z $mnt ]] && return
    [[ -d $mnt ]] || return
    [[ -d ${mnt}/var/lib/yum ]] && echo "redhat" && return
    [[ -d ${mnt}/var/lib/apt ]] && echo "debian" && return
}


install_pkg(){
    Log "$FUNCNAME unimplemented"
    return 1
}


logging_init(){
    if $log_to_syslog
    then
        LOGGERCMD="/bin/logger -t ${prog}[$$]:[${extra_log_tag}] -p ${syslog_level}"
    fi
}
