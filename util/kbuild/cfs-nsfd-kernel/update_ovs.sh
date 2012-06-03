#!/bin/sh
# Re-build OVS for the kernel version defined below.

OVS_DIR=~/openvswitch
KERNEL_VER=`uname -r`
#KERNEL_VER=2.6.35-with-cfs
PROCESSORS=`grep -c ^processor /proc/cpuinfo`
cd $OVS_DIR
./configure --with-linux=/lib/modules/${KERNEL_VER}/build && \
sudo make -j${PROCESSORS} && \
sudo cp ./datapath/linux/openvswitch_mod.ko /lib/modules/${KERNEL_VER}/kernel/drivers/net && \
echo "Running depmod..."
sudo depmod -a ${KERNEL_VER}

