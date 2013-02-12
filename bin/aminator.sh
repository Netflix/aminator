#!/bin/bash
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
