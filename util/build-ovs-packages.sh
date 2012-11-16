#!/bin/bash

# Attempt to build debian packages for OVS

set -e  # exit on error
set -u  # exit on undefined variable

kvers=`uname -r`
ksrc=/lib/modules/$kvers/build
dist=`lsb_release -is | tr [A-Z] [a-z]`
release=`lsb_release -rs`
arch=`uname -m`
buildsuffix=-2
if [ "$arch" = "i686" ]; then arch=i386; fi
if [ "$arch" = "x86_64" ]; then arch=amd64; fi

overs=1.4.0
ovs=openvswitch-$overs
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
 if [ "$release" = "10.04" ]; then
  # Lucid doesn't seem to have all the packages for ovsdbmonitor
  echo "*** Patching debian/rules to remove dh_python2"
  sed -i -e 's/dh_python2/dh_pysupport/' debian/rules
  echo "*** Not building ovsdbmonitor since it's too hard on 10.04"
  mv debian/ovsdbmonitor.install debian/ovsdbmonitor.install.backup
  sed -i -e 's/ovsdbmonitor.install/ovsdbmonitor.install.backup/' Makefile.in
 else
  # Install a bag of hurt for ovsdbmonitor
  $install python-pyside.qtcore pyqt4-dev-tools python-twisted python-twisted-bin \
   python-twisted-core python-twisted-conch python-anyjson python-zope.interface
 fi
 # init script was written to assume that commands complete
 sed -i -e 's/^set -e/#set -e/' debian/openvswitch-controller.init

echo "*** Building OVS user packages"
 opts=--with-linux=/lib/modules/`uname -r`/build
 fakeroot make -f debian/rules DATAPATH_CONFIGURE_OPTS=$opts binary

echo "*** Building OVS datapath kernel module package"
 # Still looking for the "right" way to do this...
 sudo mkdir -p /usr/src/linux
 ln -sf _debian/openvswitch.tar.gz .
 sudo make -f debian/rules.modules KSRC=$ksrc KVERS=$kvers binary-modules

echo "*** Built the following packages:"
 cd ~
 ls -l *deb

archive=ovs-$overs-core-$dist-$release-$arch$buildsuffix.tar
ovsbase='common pki switch brcompat controller datapath-dkms'
echo "*** Packing up $ovsbase .debs into:"
echo "    $archive"
 pkgs=""
 for component in $ovsbase; do
  if echo $component | egrep 'dkms|pki'; then
    # Architecture-independent packages
    deb=(openvswitch-${component}_$overs*all.deb)
  else
    deb=(openvswitch-${component}_$overs*$arch.deb)
  fi
  pkgs="$pkgs $deb"
 done
 rm -rf $archive
 tar cf $archive $pkgs

echo "*** Contents of archive $archive:"
 tar tf $archive

echo "*** Done (hopefully)"

