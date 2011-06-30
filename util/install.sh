#!/usr/bin/env bash
# Mininet install script for Debian
# Brandon Heller (brandonh@stanford.edu)

# Fail on error
set -e
 
# Fail on unset var usage
set -o nounset

# Location of CONFIG_NET_NS-enabled kernel(s)
KERNEL_LOC=http://www.openflow.org/downloads/mininet

test -e /etc/debian_version && DIST="Debian"
grep Ubuntu /etc/lsb-release &> /dev/null && DIST="Ubuntu"

# Kernel params

if [ "$DIST" = "Debian" ]; then
    KERNEL_NAME=2.6.33.1-mininet
    KERNEL_HEADERS=linux-headers-${KERNEL_NAME}_${KERNEL_NAME}-10.00.Custom_i386.deb
    KERNEL_IMAGE=linux-image-${KERNEL_NAME}_${KERNEL_NAME}-10.00.Custom_i386.deb
elif [ "$DIST" = "Ubuntu" ]; then
    KERNEL_NAME=`uname -r`
    KERNEL_HEADERS=linux-headers-${KERNEL_NAME}
else
    echo "Install.sh currently only supports Ubuntu and Debian."
    exit 1
fi

echo "Detected Linux distribution: $DIST"

# Kernel Deb pkg to be removed:
KERNEL_IMAGE_OLD=linux-image-2.6.26-2-686

DRIVERS_DIR=/lib/modules/${KERNEL_NAME}/kernel/drivers/net

OVS_RELEASE=v1.1.1
OVS_DIR=~/openvswitch
OVS_KMOD=openvswitch_mod.ko

function kernel {
	echo "Install Mininet-compatible kernel"
	sudo apt-get update
    
    if [ "$DIST" = "Debian" ]; then
    
	# The easy approach: download pre-built linux-image and linux-headers packages:
	wget -c $KERNEL_LOC/$KERNEL_HEADERS
	wget -c $KERNEL_LOC/$KERNEL_IMAGE

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
    fi

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
	echo "Installing Mininet dependencies"
	sudo aptitude install -y gcc make screen psmisc xterm ssh iperf iproute \
        python-setuptools python-networkx

    if [ "$DIST" = "Ubuntu" ] && [ "`lsb_release -sr`" = "10.04" ]; then
        echo "Upgrading networkx to avoid deprecation warning"
        sudo easy_install --upgrade networkx
    fi

	#Add sysctl parameters as noted in the INSTALL file to increase kernel limits to support larger setups:
	sudo su -c "cat $HOME/mininet/util/sysctl_addon >> /etc/sysctl.conf"

	#Load new sysctl settings:
	sudo sysctl -p
    
    echo "Installing Mininet core"
    pushd ~/mininet
    sudo make install
    popd
}

# The following will cause a full OF install, covering:
# -user switch
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

    # Patch controller to handle more than 16 switches
    patch -p1 < ~/mininet/util/openflow-patches/controller.patch

	# Resume the install:
	./boot.sh
	./configure
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

	# Disable IPv6.  Add to /etc/modprobe.d/blacklist:
    if [ "$DIST" = "Ubuntu" ]; then
        BLACKLIST=/etc/modprobe.d/blacklist.conf
    else
        BLACKLIST=/etc/modprobe.d/blacklist
    fi
	sudo sh -c "echo 'blacklist net-pf-10\nblacklist ipv6' >> $BLACKLIST"
}

# Install OpenVSwitch
# Instructions derived from OVS INSTALL, INSTALL.OpenFlow and README files.
function ovs {
	echo "Installing OpenVSwitch..."

    if [ "$DIST" = "Debian" ]; then
        sudo aptitude -y install pkg-config gcc make git-core python-dev libssl-dev
        #Install Autoconf 2.63+ backport from Debian Backports repo:
        #Instructions from http://backports.org/dokuwiki/doku.php?id=instructions
        sudo su -c "echo 'deb http://www.backports.org/debian lenny-backports main contrib non-free' >> /etc/apt/sources.list"
        sudo apt-get update
        sudo apt-get -y --force-yes install debian-backports-keyring
        sudo apt-get -y --force-yes -t lenny-backports install autoconf
    fi

    if [ "$DIST" = "Ubuntu" ]; then
        sudo apt-get -y install $KERNEL_HEADERS
    fi

	#Install OVS from release
	cd ~/
	git clone git://openvswitch.org/openvswitch
	cd $OVS_DIR
    git checkout $OVS_RELEASE
	./boot.sh
    BUILDDIR=/lib/modules/${KERNEL_NAME}/build
    if [ ! -e $BUILDDIR ]; then
        echo "Creating build sdirectory $BUILDDIR"
        sudo mkdir -p $BUILDDIR
    fi
    opts="--with-l26=$BUILDDIR"
	./configure $opts
	make
	sudo make install
}

# Install NOX with tutorial files
function nox {
	echo "Installing NOX w/tutorial files..."

	#Install NOX deps:
	sudo apt-get -y install autoconf automake g++ libtool python python-twisted swig  libxerces-c2-dev libssl-dev make
    if [ "$DIST" = "Debian" ]; then
        sudo apt-get -y install libboost1.35-dev
    elif [ "$DIST" = "Ubuntu" ]; then
        sudo apt-get -y install python-dev libboost-dev 
        sudo apt-get -y install libboost-filesystem-dev
        sudo apt-get -y install libboost-test-dev
    fi
	#Install NOX optional deps:
	sudo apt-get install -y libsqlite3-dev python-simplejson

	#Install NOX:
	cd ~/
	git clone git://openflowswitch.org/nox-tutorial noxcore
	cd noxcore

	# With later autoconf versions this doesn't quite work:
	./boot.sh --apps-core || true
    if [ "$DIST" = "Debian" ]; then
        # So use this instead:
        autoreconf --install --force
    fi
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

# Install OFtest
function oftest {
    echo "Installing oftest..."

    #Install deps:
    sudo apt-get install -y tcpdump python-scapy

    #Install oftest:
    cd ~/
    git clone git://openflow.org/oftest
    cd oftest
    cd tools/munger
    sudo make install
}

# Install cbench
function cbench {
    echo "Installing cbench..."
    
    sudo apt-get install -y libsnmp-dev libpcap-dev
    cd ~/
    git clone git://openflow.org/oflops.git
    cd oflops
    sh boot.sh || true # possible error in autoreconf, so run twice
    sh boot.sh
    ./configure --with-openflow-src-dir=$HOME/openflow
    make
    sudo make install || true # make install fails; force past this
}

function other {
	echo "Doing other setup tasks..."

	#Enable command auto completion using sudo; modify ~/.bashrc:
	sed -i -e 's|# for examples$|&\ncomplete -cf sudo|' ~/.bashrc

	#Install tcpdump and tshark, cmd-line packet dump tools.  Also install gitk,
	#a graphical git history viewer.
	sudo apt-get install -y tcpdump tshark gitk

    #Install common text editors
    sudo apt-get install -y vim nano emacs

    #Install NTP
    sudo apt-get install -y ntp

	#Set git to colorize everything.
	git config --global color.diff auto
	git config --global color.status auto
	git config --global color.branch auto

	#Reduce boot screen opt-out delay. Modify timeout in /boot/grub/menu.lst to 1:
    if [ "$DIST" = "Debian" ]; then
        sudo sed -i -e 's/^timeout.*$/timeout         1/' /boot/grub/menu.lst
    fi

    # Clean unneeded debs:
    rm -f ~/linux-headers-* ~/linux-image-*
}

# Script to copy built OVS kernel module to where modprobe will
# find them automatically.  Removes the need to keep an environment variable
# for insmod usage, and works nicely with multiple kernel versions.
#
# The downside is that after each recompilation of OVS you'll need to
# re-run this script.  If you're using only one kernel version, then it may be
# a good idea to use a symbolic link in place of the copy below.
function modprobe {
	echo "Setting up modprobe for OVS kmod..."

	sudo cp $OVS_DIR/datapath/linux-2.6/$OVS_KMOD $DRIVERS_DIR
	sudo depmod -a ${KERNEL_NAME}
}

function all {
	echo "Running all commands..."
    if [ "$DIST" != "Ubuntu" ]; then
        # Ubuntu ships with Mininet-compatible kernel
        kernel
    fi
	mn_deps
	of
	ovs
    modprobe
	nox
	oftest
	cbench
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
	history -c  # note this won't work if you have multiple bash sessions
	rm -f ~/.bash_history  # need to clear in memory and remove on disk
	rm -f ~/.ssh/id_rsa* ~/.ssh/known_hosts
	sudo rm -f ~/.ssh/authorized_keys2

	# Remove Mininet files
	#sudo rm -f /lib/modules/python2.5/site-packages/mininet*
	#sudo rm -f /usr/bin/mnexec

	# Clear optional dev script for SSH keychain load on boot
	rm -f ~/.bash_profile

	# Clear git changes
	git config --global user.name "None"
	git config --global user.email "None"

	# Remove mininet install script
	rm -f install-mininet.sh
}

function usage {
    printf 'Usage: %s [-acdfhkmntvxy]\n\n' $(basename $0) >&2
    
    printf 'This install script attempts to install useful packages\n' >&2
    printf 'for Mininet. It should (hopefully) work on Ubuntu 10.04 and\n' >&2
    printf 'Debian 5.0 (Lenny). If you run into trouble, try\n' >&2
    printf 'installing one thing at a time, and looking at the \n' >&2
    printf 'specific installation function in this script.\n\n' >&2
        
    printf 'options:\n' >&2
    printf -- ' -a: (default) install (A)ll packages - good luck!\n' >&2
    printf -- ' -b: install controller (B)enchmark (oflops)\n' >&2
    printf -- ' -c: (C)lean up after kernel install\n' >&2
    printf -- ' -d: (D)elete some sensitive files from a VM image\n' >&2    
    printf -- ' -f: install open(F)low\n' >&2
    printf -- ' -h: print this (H)elp message\n' >&2
    printf -- ' -k: install new (K)ernel\n' >&2
    printf -- ' -m: install Open vSwitch kernel (M)odule\n' >&2
    printf -- ' -n: install mini(N)et dependencies + core files\n' >&2
    printf -- ' -t: install o(T)her stuff\n' >&2
    printf -- ' -v: install open (V)switch\n' >&2
    printf -- ' -x: install NO(X) OpenFlow controller\n' >&2
    printf -- ' -y: install (A)ll packages\n' >&2    
    
    exit 2
}

if [ $# -eq 0 ]
then
	all
else
	while getopts 'abcdfhkmntvx' OPTION
	do
	  case $OPTION in
	  a)    all;;
	  b)    cbench;;
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
	  ?)    usage;;
	  esac
	done
	shift $(($OPTIND - 1))
fi
