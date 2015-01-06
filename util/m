#!/bin/bash

# Attach to a Mininet host and run a command

if [ -z $1 ]; then
  echo "usage: $0 host cmd [args...]"
  exit 1
else
  host=$1
fi

pid=`ps ax | grep "mininet:$host$" | grep bash | grep -v mnexec | awk '{print $1};'`

if echo $pid | grep -q ' '; then
  echo "Error: found multiple mininet:$host processes"
  exit 2
fi

if [ "$pid" == "" ]; then
  echo "Could not find Mininet host $host"
  exit 3
fi

if [ -z $2 ]; then
  cmd='bash'
else
  shift
  cmd=$*
fi

cgroup=/sys/fs/cgroup/cpu/$host
if [ -d "$cgroup" ]; then
  cg="-g $host"
fi

# Check whether host should be running in a chroot dir
rootdir="/var/run/mn/$host/root"
if [ -d $rootdir -a -x $rootdir/bin/bash ]; then
    cmd="'cd `pwd`; exec $cmd'"
    cmd="chroot $rootdir /bin/bash -c $cmd"
fi

cmd="exec sudo mnexec $cg -a $pid $cmd"
eval $cmd
