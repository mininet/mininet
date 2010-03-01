#!/bin/sh
#Brandon Heller (brandonh@stanford.edu)
#Install OpenFlow and tools on Debian Lenny

#The following will cause a full OF install, with both user and kernel switch, dissector, tests, and everything.

#The instructions below are an abbreviated version from [[http://www.openflowswitch.org/wk/index.php/Debian_Install][ !OpenFlow Debian install instructions]], modified to use Debian Lenny rather than unstable.

sudo apt-get install -y git-core automake m4 pkg-config libtool make libc6-dev autoconf autotools-dev gcc
git clone git://openflowswitch.org/openflow.git
cd ~/openflow

#Switch to a temporary branch that should work on Debian Lenny.
git checkout -b debianfix origin/debianfix

#Install deps:
sudo regress/scripts/install_deps.pl

#Resume the install:
git fetch
git checkout -b release/0.8.9 origin/release/0.8.9
./boot.sh
./configure --with-l26=/lib/modules/`uname -r`
make
sudo make install

#Modify /etc/rc.local to auto-add the ofdatapath kmod on boot, as well as auto-add the tun module (used by user-space datapath to create a local switch port):
sudo sed -i -e 's|# By default this script does nothing.|&\nmodprobe tun\ninsmod /home/mininet/openflow/datapath/linux-2.6/ofdatapath.ko|' /etc/rc.local

#Run both commands now, before trying mininet:
sudo modprobe tun
sudo insmod /home/mininet/openflow/datapath/linux-2.6/ofdatapath.ko

#Install dissector:
sudo apt-get install -y wireshark libgtk2.0-dev
cd ~/openflow/utilities/wireshark_dissectors/openflow
make
sudo make install

#Remove avahi-daemon, which may cause unwanted discovery packets to be sent during tests, near link status changes:
sudo apt-get remove -y avahi-daemon

#Disable IPv6.  Add to /etc/modprobe.d/blacklist.conf:
sudo sh -c "echo -e 'blacklist net-pf-10\nblacklist ipv6' > /etc/modprobe.d/blacklist.conf"

#Enable command auto completion using sudo; modify ~/.bashrc:
sudo sed -i -e 's|# for examples$|&\ncomplete -cf sudo|' ~/.bashrc
