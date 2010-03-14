#!/bin/sh
# Script to copy built OVS and OF kernel modules to where modprobe will
# find them automatically.  Removes the need to keep an environment variable
# for each, and works nicely with multiple kernel versions.
#
# The downside is that after each recompilation of OVS or OF you'll need to
# re-run this script.  If you're using only one kernel version, then it may be
# a good idea to use a symbolic link in place of the copy below.
DRIVERS_DIR=/lib/modules/`uname -r`/kernel/drivers

OVS_DIR=~/openvswitch
OVS_KMOD=openvswitch_mod.ko
cp $OVS_DIR/datapath/linux-2.6/$OVS_KMOD $DRIVERS_DIR

OF_DIR=~/openflow
OF_KMOD=ofdatapath.ko
cp $OF_DIR/datapath/linux-2.6/$OF_KMOD $DRIVERS_DIR

# Update for modprobe
sudo depmod -a
