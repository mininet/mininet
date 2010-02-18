#!/bin/sh
#Brandon Heller (brandonh@stanford.edu)
#Install OVS on Debian Lenny

#The following files were useful for the install process:
#OVS INSTALL file:
#http://openvswitch.org/cgi-bin/gitweb.cgi?p=openvswitch;a=blob_plain;f=INSTALL.Linux;hb=HEAD

#OVS OpenFlow INSTALL file:
#http://openvswitch.org/cgi-bin/gitweb.cgi?p=openvswitch;a=blob_plain;f=INSTALL.OpenFlow;hb=HEAD

#OVS README file:
#http://openvswitch.org/cgi-bin/gitweb.cgi?p=openvswitch;a=blob_plain;f=README;hb=HEAD

#Install Autoconf 2.63 from source (a more recent version than that in the Deb repositories is required).  This should be the only extra dependency.
cd ~/
wget http://ftp.gnu.org/gnu/autoconf/autoconf-2.63.tar.bz2
tar xjf autoconf-2.63.tar.bz2
cd autoconf-2.63/
./configure
make
sudo make install
cd ~/
rm -rf autoconf*

#Install OVS:
git clone git://openvswitch.org/openvswitch
cd openvswitch
./boot.sh
./configure --with-l26=/lib/modules/`uname -r`/build
make
sudo make install