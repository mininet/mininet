#!/usr/bin/env bash

# script to clean up after cluster edition authentication

user=$(whoami)
SSHDIR=/tmp/mn/ssh
usage=$'./authenticate [ -h ] [ host1 ] [ host2 ] ... \n
        Tear down a mininet cluster after using ./authenticate to 
        set up temporary ssh'

if [ -z "$1" ]; then
    echo "ERROR: Must input a hostname"
    echo "$usage"
    exit
fi

if [ "$1" == "-h" ]; then
    echo "$usage"
    exit
fi

for i in "$@"; do
    output=$(getent ahostsv4 "$i")
    if [ -z "$output" ]; then
        echo "***WARNING: could not find hostname "$i""
        echo ""
    else
        hosts+="$i "
    fi
done

for host in $hosts; do
    echo "***cleaning up $host"
    sudo ssh $user@$host "sudo umount /home/$user/.ssh
                          sudo umount /root/.ssh
                          sudo rm -rf $SSHDIR"
done
echo "**unmounting local directories"
sudo umount /home/$user/.ssh
sudo umount /root/.ssh
echo "***removing temporary ssh directory"
sudo rm -rf $SSHDIR
echo "done!"
