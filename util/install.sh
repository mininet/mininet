#!/usr/bin/env bash
# Mininet install script for Debian
# Brandon Heller (brandonh@stanford.edu)

# Fail on error
set -e

# Fail on unset var usage
set -o nounset

# Location of CONFIG_NET_NS-enabled kernel(s)
KERNEL_LOC=http://www.stanford.edu/~brandonh

# Kernel params
# These kernels have been tried:
KERNEL_NAME=2.6.29.6-custom
#KERNEL_NAME=2.6.33-custom
#KERNEL_NAME=2.6.33.1-custom
#KERNEL_NAME=`uname -r`
KERNEL_HEADERS=linux-headers-${KERNEL_NAME}_${KERNEL_NAME}-10.00.Custom_i386.deb
KERNEL_IMAGE=linux-image-${KERNEL_NAME}_${KERNEL_NAME}-10.00.Custom_i386.deb

# Kernel Deb pkg to be removed:
KERNEL_IMAGE_OLD=linux-image-2.6.26-2-686

DRIVERS_DIR=/lib/modules/${KERNEL_NAME}/kernel/drivers

OVS_RELEASE=openvswitch-0.99.2
#OVS_RELEASE=openvswitch
OVS_DIR=~/$OVS_RELEASE
OVS_KMOD=openvswitch_mod.ko
OF_DIR=~/openflow
OF_KMOD=ofdatapath.ko

function kernel {
	echo "Install new kernel..."
	sudo apt-get update

	# The easy approach: download pre-built linux-image and linux-headers packages:
	wget $KERNEL_LOC/$KERNEL_HEADERS
	wget $KERNEL_LOC/$KERNEL_IMAGE

	#Install custom linux headers and image:
	sudo dpkg -i $KERNEL_IMAGE $KERNEL_HEADERS

	# The next two steps are to work around a bug in newer versions of
	# kernel-package, which fails to add initrd images with the latest kernels.
	# See http://bugs.debian.org/cgi-bin/bugreport.cgi?bug=525032
	# Generate initrd image if the .deb didn't install it:
	if ! test -e /boot/initrd.img-${KERNEL_NAME}; then
		sudo update-initramfs -c -k ${KERNEL_NAME}
	fi
	
	# Ensure /boot/grub/menu.lst boots with initrd image:
	sudo update-grub

	# The default should be the new kernel. Otherwise, you may need to modify /boot/grub/menu.lst to set the default to the entry corresponding to the kernel you just installed.
}

function kernel_clean {
	echo "Cleaning kernel..."

	# To save disk space, remove previous kernel
	sudo apt-get -y remove $KERNEL_IMAGE_OLD

	#Also remove downloaded packages:
	rm -f ~/linux-headers-* ~/linux-image-*
}

# Install Mininet deps
function mn_deps {
	#Install dependencies:
	sudo apt-get install -y screen psmisc xterm ssh iperf iproute python-setuptools

	#Add sysctl parameters as noted in the INSTALL file to increase kernel limits to support larger setups:
	sudo su -c "cat /home/mininet/mininet/util/sysctl_addon >> /etc/sysctl.conf"

	#Load new sysctl settings:
	sudo sysctl -p
}

# The following will cause a full OF install, covering:
# -user switch
# -kernel switch
# -dissector
# The instructions below are an abbreviated version from
# http://www.openflowswitch.org/wk/index.php/Debian_Install
# ... modified to use Debian Lenny rather than unstable.
function of {
	echo "Installing OpenFlow and its tools..."

	cd ~/
	sudo apt-get install -y git-core automake m4 pkg-config libtool make libc6-dev autoconf autotools-dev gcc
	git clone git://openflowswitch.org/openflow.git
	cd ~/openflow
	git fetch

	# Get debianfix branch, which doesn't break on test deps install
	# This is an optional step.
	git checkout -b debianfix origin/debianfix
	sudo regress/scripts/install_deps.pl

	# Resume the install:
	git checkout -b release/0.8.9 origin/release/0.8.9
	./boot.sh
	./configure --with-l26=/lib/modules/${KERNEL_NAME}
	make
	sudo make install

	# Install dissector:
	sudo apt-get install -y wireshark libgtk2.0-dev
	cd ~/openflow/utilities/wireshark_dissectors/openflow
	make
	sudo make install

	# Copy coloring rules: OF is white-on-blue:
	mkdir -p ~/.wireshark
	cp ~/mininet/util/colorfilters ~/.wireshark

	# Remove avahi-daemon, which may cause unwanted discovery packets to be sent during tests, near link status changes:
	sudo apt-get remove -y avahi-daemon

	# Disable IPv6.  Add to /etc/modprobe.d/blacklist.conf:
	sudo sh -c "echo -e 'blacklist net-pf-10\nblacklist ipv6' >> /etc/modprobe.d/blacklist.conf"
}

# Install OpenVSwitch
# Instructions derived from OVS INSTALL, INSTALL.OpenFlow and README files.
function ovs {
	echo "Installing OpenVSwitch..."

	#Install Autoconf 2.63+ backport from Debian Backports repo:
	#Instructions from http://backports.org/dokuwiki/doku.php?id=instructions
	sudo su -c "echo 'deb http://www.backports.org/debian lenny-backports main contrib non-free' >> /etc/apt/sources.list"
	sudo apt-get update
	sudo apt-get -y --force-yes install debian-backports-keyring
	sudo apt-get -y --force-yes -t lenny-backports install autoconf

	#Install OVS from git
	#git clone git://openvswitch.org/openvswitch
	#cd openvswitch
	#./boot.sh

	#Install OVS from release
	cd ~/
	wget http://openvswitch.org/releases/${OVS_RELEASE}.tar.gz
	tar xzf ${OVS_RELEASE}.tar.gz
	cd $OVS_RELEASE

	./configure --with-l26=/lib/modules/${KERNEL_NAME}/build
	make
	sudo make install
}

# Install NOX
function nox {
	echo "Install NOX..."

	#Install NOX deps:
	sudo apt-get -y install autoconf automake g++ libtool python python-twisted swig libboost1.35-dev libxerces-c2-dev libssl-dev make

	#Install NOX optional deps:
	sudo apt-get install -y libsqlite3-dev python-simplejson

	#Install NOX:
	cd ~/
	git clone git://noxrepo.org/noxcore
	cd noxcore

	# With later autoconf versions this doesn't quite work:
	./boot.sh || true
	# So use this instead:
	autoreconf --install --force
	mkdir build
	cd build
	../configure --with-python=yes
	make
	#make check

	# Add NOX_CORE_DIR env var:
	sed -i -e 's|# for examples$|&\nexport NOX_CORE_DIR=~/noxcore/build/src|' ~/.bashrc

	# To verify this install:
	#cd ~/noxcore/build/src
    #./nox_core -v -i ptcp:
}

function other {
	echo "Doing other setup tasks..."

	#Enable command auto completion using sudo; modify ~/.bashrc:
	sed -i -e 's|# for examples$|&\ncomplete -cf sudo|' ~/.bashrc

	#Install tcpdump and tshark, cmd-line packet dump tools.  Also install gitk,
	#a graphical git history viewer.
	sudo apt-get install -y tcpdump tshark gitk

	#Set git to colorize everything.
	git config --global color.diff auto
	git config --global color.status auto
	git config --global color.branch auto

	#Reduce boot screen opt-out delay. Modify timeout in /boot/grub/menu.lst to 1:
	sudo sed -i -e 's/^timeout.*$/timeout         1/' /boot/grub/menu.lst
}

# The OpenFlow ref kmod is broken with 2.6.33 and CONFIG_NET_NS=y.  This is a
# reported bug: http://www.openflowswitch.org/bugs/openflow/ticket/82
function of_33 {
	echo "Installing OpenFlow..."
	cd ~/
	cd openflow
	git checkout -b fix-2.6.33 origin/devel-0.8.9/fix-2.6.33
	./boot.sh
	./configure --with-l26=/lib/modules/${KERNEL_NAME}
	make
	sudo make install
}

# OVS v0.99.2 does not build on 2.6.33, and the master branch of OVS includes
# patches for OF1.0 support.  It doesn't look like there's a supported branch
# for v0.99, so the script below applies a patch for this.
# Since the patch is in a makefile, we'll have to steal the makefile builder,
# boot.sh, from the OVS git repo.
function ovs_33 {
	echo "Installing OpenVSwitch..."
	cd ~/
	git clone git://openvswitch.org/openvswitch
	cp openvswitch/boot.sh $OVS_RELEASE
	rm -rf openvswitch
	cd ~/$OVS_RELEASE
	git apply ~/mininet/util/ovs-fix-2.6.33.patch
	./boot.sh
	./configure --with-l26=/lib/modules/${KERNEL_NAME}/build
	make
	sudo make install
}

function linux_33 {
    kernel
	of_33
	ovs_33
	modprobe

	# Clean unneeded debs:
	rm -f ~/linux-headers-* ~/linux-image-*
}

# Script to copy built OVS and OF kernel modules to where modprobe will
# find them automatically.  Removes the need to keep an environment variable
# for each, and works nicely with multiple kernel versions.
#
# The downside is that after each recompilation of OVS or OF you'll need to
# re-run this script.  If you're using only one kernel version, then it may be
# a good idea to use a symbolic link in place of the copy below.
function modprobe {
	echo "Setting up modprobe for OVS kmod..."
	sudo cp $OVS_DIR/datapath/linux-2.6/$OVS_KMOD $DRIVERS_DIR

	echo "Setting up modprobe for OF kmod..."
	sudo cp $OF_DIR/datapath/linux-2.6/$OF_KMOD $DRIVERS_DIR

	sudo depmod -a ${KERNEL_NAME}
}

function all {
	echo "Running all commands..."
	kernel
	mn_deps
	of
	ovs
	modprobe
	nox
	other
	echo "Please reboot, then run ./mininet/util/install.sh -c to remove unneeded packages."
	echo "Enjoy Mininet!"
}

# Restore disk space and remove sensitive files before shipping a VM.
function vm_clean {
	echo "Cleaning VM..."
	sudo apt-get clean
	sudo rm -rf /tmp/*
	sudo rm -rf openvswitch*.tar.gz

	# Remove sensistive files
	history -c
	rm ~/.ssh/id_rsa*
	sudo rm ~/.ssh/authorized_keys2

	# Remove Mininet files
	sudo rm -rf ~/mininet
	sudo rm /lib/modules/python2.5/site-packages/mininet*
	sudo rm /usr/bin/mnexec

	# Clear git changes
	git config --global user.name "None"
	git config --global user.email "None"

}

function usage {
    printf "Usage: %s: [-acdfhkmntvxy] args\n" $(basename $0) >&2
    exit 2
}

if [ $# -eq 0 ]
then
	all
else
	while getopts 'acdfhkmntvxy' OPTION
	do
	  case $OPTION in
	  a)    all;;
	  c)    kernel_clean;;
	  d)    vm_clean;;
	  f)    of;;
	  h)	usage;;
	  k)    kernel;;
	  m)    modprobe;;
	  n)    mn_deps;;
	  t)    other;;
	  v)    ovs;;
	  x)    nox;;
	  y)    linux_33;;
	  ?)    usage;;
	  esac
	done
	shift $(($OPTIND - 1))
fi
