#!/bin/bash

# Attempt to build debian packages for OVS

set -e  # exit on error
set -u  # exit on undefined variable

kvers=`uname -r`
ksrc=/lib/modules/$kvers/build
ovs=openvswitch-1.4.0
ovstgz=$ovs.tar.gz
ovsurl=http://openvswitch.org/releases/$ovstgz

install='sudo apt-get install -y'

echo "*** Installing debian/ubuntu build system"
 $install build-essential devscripts ubuntu-dev-tools debhelper dh-make
 $install diff patch cdbs quilt gnupg fakeroot lintian pbuilder piuparts
 $install module-assistant

echo "*** Installing OVS dependencies"
 $install pkg-config gcc make python-dev libssl-dev libtool
 $install dkms ipsec-tools

echo "*** Installing headers for $kvers"
 $install linux-headers-$kvers

echo "*** Retrieving OVS source"
 wget -c $ovsurl
 tar xzf $ovstgz
 cd $ovs

echo "*** Patching OVS source"
 # Not sure why this fails, but off it goes!
 sed -i -e 's/dh_strip/# dh_strip/' debian/rules
 # And this fails on 10.04
 if [ `lsb_release -rs` = "10.04" ]; then
  echo "*** Patching debian/rules to remove dh_python2"
  sed -i -e 's/dh_python2/dh_pysupport/' debian/rules
  echo "*** Not building ovsdbmonitor since it's too hard on 10.04"
  mv debian/ovsdbmonitor.install debian/ovsdbmonitor.install.backup
  sed -i -e 's/ovsdbmonitor.install/ovsdbmonitor.install.backup/' Makefile.in
 fi

echo "*** Building OVS user packages"
 opts=--with-linux=/lib/modules/`uname -r`/build
 fakeroot make -f debian/rules DATAPATH_CONFIGURE_OPTS=$opts binary

echo "*** Building OVS datapath kernel module package"
 # Still looking for the "right" way to do this...
 sudo mkdir -p /usr/src/linux
 ln -sf _debian/openvswitch.tar.gz .
 sudo make -f debian/rules.modules KSRC=$ksrc KVERS=$kvers binary-modules

echo "*** User packages:"
 ls -l ~/*openvswitch*deb

echo "*** Kernel packages:"
 ls -l /usr/src/*openvswitch*deb

echo "*** Done (hopefully)"










