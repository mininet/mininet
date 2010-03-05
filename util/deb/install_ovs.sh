#!/bin/sh
#Brandon Heller (brandonh@stanford.edu)
#Install OVS on Debian Lenny

#Install OVS:
git clone git://openvswitch.org/openvswitch
cd openvswitch
./boot.sh
./configure --with-l26=/lib/modules/`uname -r`/build
make