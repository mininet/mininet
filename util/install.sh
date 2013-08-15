#!/usr/bin/env bash

# Mininet install script for Ubuntu (and Debian Lenny)
# Brandon Heller (brandonh@stanford.edu)

# Fail on error
set -e

# Fail on unset var usage
set -o nounset

# Get directory containing mininet folder
MININET_DIR="$( cd -P "$( dirname "${BASH_SOURCE[0]}" )/../.." && pwd )"

# Set up build directory, which by default is the working directory
#  unless the working directory is a subdirectory of mininet, 
#  in which case we use the directory containing mininet
BUILD_DIR=$PWD
case $PWD in
  $MININET_DIR/*) BUILD_DIR=$MININET_DIR;; # currect directory is a subdirectory
  *) BUILD_DIR=$PWD;;
esac

# Location of CONFIG_NET_NS-enabled kernel(s)
KERNEL_LOC=http://www.openflow.org/downloads/mininet

# Attempt to identify Linux release

DIST=Unknown
RELEASE=Unknown
CODENAME=Unknown
ARCH=`uname -m`
if [ "$ARCH" = "x86_64" ]; then ARCH="amd64"; fi
if [ "$ARCH" = "i686" ]; then ARCH="i386"; fi

test -e /etc/debian_version && DIST="Debian"
grep Ubuntu /etc/lsb-release &> /dev/null && DIST="Ubuntu"
if [ "$DIST" = "Ubuntu" ] || [ "$DIST" = "Debian" ]; then
    install='sudo apt-get -y install'
    remove='sudo apt-get -y remove'
    pkginst='sudo dpkg -i'
    # Prereqs for this script
    if ! which lsb_release &> /dev/null; then
        $install lsb-release
    fi
    if ! which bc &> /dev/null; then
        $install bc
    fi
fi
if which lsb_release &> /dev/null; then
    DIST=`lsb_release -is`
    RELEASE=`lsb_release -rs`
    CODENAME=`lsb_release -cs`
fi
echo "Detected Linux distribution: $DIST $RELEASE $CODENAME $ARCH"

# Kernel params

if [ "$DIST" = "Ubuntu" ]; then
    if [ "$RELEASE" = "10.04" ]; then
        KERNEL_NAME='3.0.0-15-generic'
    else
        KERNEL_NAME=`uname -r`
    fi
    KERNEL_HEADERS=linux-headers-${KERNEL_NAME}
elif [ "$DIST" = "Debian" ] && [ "$ARCH" = "i386" ] && [ "$CODENAME" = "lenny" ]; then
    KERNEL_NAME=2.6.33.1-mininet
    KERNEL_HEADERS=linux-headers-${KERNEL_NAME}_${KERNEL_NAME}-10.00.Custom_i386.deb
    KERNEL_IMAGE=linux-image-${KERNEL_NAME}_${KERNEL_NAME}-10.00.Custom_i386.deb
else
    echo "Install.sh currently only supports Ubuntu and Debian Lenny i386."
    exit 1
fi

# More distribution info
DIST_LC=`echo $DIST | tr [A-Z] [a-z]` # as lower case

# Kernel Deb pkg to be removed:
KERNEL_IMAGE_OLD=linux-image-2.6.26-33-generic

DRIVERS_DIR=/lib/modules/${KERNEL_NAME}/kernel/drivers/net

OVS_RELEASE=1.4.0
OVS_PACKAGE_LOC=https://github.com/downloads/mininet/mininet
OVS_BUILDSUFFIX=-ignore # was -2
OVS_PACKAGE_NAME=ovs-$OVS_RELEASE-core-$DIST_LC-$RELEASE-$ARCH$OVS_BUILDSUFFIX.tar
OVS_TAG=v$OVS_RELEASE

IVS_TAG=v0.3

# Command-line versions overrides that simplify custom VM creation
# To use, pass in the vars on the cmd line before install.sh, e.g.
# WS_DISSECTOR_REV=pre-ws-1.10.0 install.sh -w
WS_DISSECTOR_REV=${WS_DISSECTOR_REV:-""}
OF13_SWITCH_REV=${OF13_SWITCH_REV:-""}


function kernel {
    echo "Install Mininet-compatible kernel if necessary"
    sudo apt-get update
    if [ "$DIST" = "Ubuntu" ] &&  [ "$RELEASE" = "10.04" ]; then
        $install linux-image-$KERNEL_NAME
    elif [ "$DIST" = "Debian" ]; then
        # The easy approach: download pre-built linux-image and linux-headers packages:
        wget -c $KERNEL_LOC/$KERNEL_HEADERS
        wget -c $KERNEL_LOC/$KERNEL_IMAGE

        # Install custom linux headers and image:
        $pkginst $KERNEL_IMAGE $KERNEL_HEADERS

        # The next two steps are to work around a bug in newer versions of
        # kernel-package, which fails to add initrd images with the latest kernels.
        # See http://bugs.debian.org/cgi-bin/bugreport.cgi?bug=525032
        # Generate initrd image if the .deb didn't install it:
        if ! test -e /boot/initrd.img-${KERNEL_NAME}; then
            sudo update-initramfs -c -k ${KERNEL_NAME}
        fi

        # Ensure /boot/grub/menu.lst boots with initrd image:
        sudo update-grub

        # The default should be the new kernel. Otherwise, you may need to modify
        # /boot/grub/menu.lst to set the default to the entry corresponding to the
        # kernel you just installed.
    fi
}

function kernel_clean {
    echo "Cleaning kernel..."

    # To save disk space, remove previous kernel
    if ! $remove $KERNEL_IMAGE_OLD; then
        echo $KERNEL_IMAGE_OLD not installed.
    fi

    # Also remove downloaded packages:
    rm -f $HOME/linux-headers-* $HOME/linux-image-*
}

# Install Mininet deps
function mn_deps {
    echo "Installing Mininet dependencies"
    $install gcc make socat psmisc xterm ssh iperf iproute telnet \
        python-setuptools cgroup-bin ethtool help2man \
        pyflakes pylint pep8

    echo "Installing Mininet core"
    pushd $MININET_DIR/mininet
    sudo make install
    popd
}

# Install Mininet developer dependencies
function mn_dev {
    echo "Installing Mininet developer dependencies"
    $install doxygen doxypy texlive-fonts-recommended
}

# The following will cause a full OF install, covering:
# -user switch
# The instructions below are an abbreviated version from
# http://www.openflowswitch.org/wk/index.php/Debian_Install
# ... modified to use Debian Lenny rather than unstable.
function of {
    echo "Installing OpenFlow reference implementation..."
    cd $BUILD_DIR/
    $install git-core autoconf automake autotools-dev pkg-config \
		make gcc libtool libc6-dev
    git clone git://openflowswitch.org/openflow.git
    cd $BUILD_DIR/openflow

    # Patch controller to handle more than 16 switches
    patch -p1 < $MININET_DIR/mininet/util/openflow-patches/controller.patch

    # Resume the install:
    ./boot.sh
    ./configure
    make
    sudo make install
    cd $BUILD_DIR
}

function of13 {
    echo "Installing OpenFlow 1.3 soft switch implementation..."
    cd $BUILD_DIR/
    $install  git-core autoconf automake autotools-dev pkg-config \
        make gcc g++ libtool libc6-dev cmake libpcap-dev libxerces-c2-dev  \
        unzip libpcre3-dev flex bison libboost-dev

    if [ ! -d "ofsoftswitch13" ]; then
        git clone https://github.com/CPqD/ofsoftswitch13.git
        if [[ -n "$OF13_SWITCH_REV" ]]; then
            cd ofsoftswitch13
            git checkout ${OF13_SWITCH_REV}
            cd ..
        fi
    fi

    # Install netbee
    NBEESRC="nbeesrc-jan-10-2013"
    NBEEURL=${NBEEURL:-http://www.nbee.org/download/}
    wget -nc ${NBEEURL}${NBEESRC}.zip
    unzip ${NBEESRC}.zip
    cd ${NBEESRC}/src
    cmake .
    make
    cd $BUILD_DIR/
    sudo cp ${NBEESRC}/bin/libn*.so /usr/local/lib
    sudo ldconfig
    sudo cp -R ${NBEESRC}/include/ /usr/

    # Resume the install:
    cd $BUILD_DIR/ofsoftswitch13
    ./boot.sh
    ./configure
    make
    sudo make install
    cd $BUILD_DIR
}

function wireshark_version_check {
    # Check Wireshark version
    WS=$(which wireshark)
    WS_VER_PATCH=(1 10) # targetting wireshark 1.10.0
    WS_VER=($($WS --version | sed 's/[a-z ]*\([0-9]*\).\([0-9]*\).\([0-9]*\).*/\1 \2 \3/'))
    if [ "${WS_VER[0]}" -lt "${WS_VER_PATCH[0]}" ] ||
       [[ "${WS_VER[0]}" -le "${WS_VER_PATCH[0]}" && "${WS_VER[1]}" -lt "${WS_VER_PATCH[1]}" ]]
    then
        # pre-1.10.0 wireshark
        echo "Setting revision: pre-ws-1.10.0"
        WS_DISSECTOR_REV="pre-ws-1.10.0" 
    fi
}

function wireshark {
    echo "Installing Wireshark dissector..."

    sudo apt-get install -y wireshark tshark libgtk2.0-dev

    if [ "$DIST" = "Ubuntu" ] && [ "$RELEASE" != "10.04" ]; then
        # Install newer version
        sudo apt-get install -y scons mercurial libglib2.0-dev
        sudo apt-get install -y libwiretap-dev libwireshark-dev
        cd $BUILD_DIR
        hg clone https://bitbucket.org/barnstorm/of-dissector
        if [[ -z "$WS_DISSECTOR_REV" ]]; then
            wireshark_version_check
        fi
        cd of-dissector
        if [[ -n "$WS_DISSECTOR_REV" ]]; then
            hg checkout ${WS_DISSECTOR_REV}
        fi
        # Build dissector
        cd src
        export WIRESHARK=/usr/include/wireshark
        scons
        # libwireshark0/ on 11.04; libwireshark1/ on later
        WSDIR=`ls -d /usr/lib/wireshark/libwireshark* | head -1`
        WSPLUGDIR=$WSDIR/plugins/
        sudo cp openflow.so $WSPLUGDIR
        echo "Copied openflow plugin to $WSPLUGDIR"
    else
        # Install older version from reference source
        cd $BUILD_DIR/openflow/utilities/wireshark_dissectors/openflow
        make
        sudo make install
    fi

    # Copy coloring rules: OF is white-on-blue:
    mkdir -p $HOME/.wireshark
    cp $MININET_DIR/mininet/util/colorfilters $HOME/.wireshark
}


# Install Open vSwitch
# Instructions derived from OVS INSTALL, INSTALL.OpenFlow and README files.

function ovs {
    echo "Installing Open vSwitch..."

    OVS_SRC=$BUILD_DIR/openvswitch
    OVS_BUILD=$OVS_SRC/build-$KERNEL_NAME
    OVS_KMODS=($OVS_BUILD/datapath/linux/{openvswitch_mod.ko,brcompat_mod.ko})

    # Required for module build/dkms install
    $install $KERNEL_HEADERS

    ovspresent=0

    # First see if we have packages
    # XXX wget -c seems to fail from github/amazon s3
    cd /tmp
    if wget $OVS_PACKAGE_LOC/$OVS_PACKAGE_NAME 2> /dev/null; then
	$install patch dkms fakeroot python-argparse
        tar xf $OVS_PACKAGE_NAME
        orig=`tar tf $OVS_PACKAGE_NAME`
        # Now install packages in reasonable dependency order
        order='dkms common pki openvswitch-switch brcompat controller'
        pkgs=""
        for p in $order; do
            pkg=`echo "$orig" | grep $p`
	    # Annoyingly, things seem to be missing without this flag
            $pkginst --force-confmiss $pkg
        done
        ovspresent=1
    fi

    # Otherwise try distribution's OVS packages
    if [ "$DIST" = "Ubuntu" ] && [ `expr $RELEASE '>=' 11.10` = 1 ]; then
        if ! dpkg --get-selections | grep openvswitch-datapath; then
            # If you've already installed a datapath, assume you
            # know what you're doing and don't need dkms datapath.
            # Otherwise, install it.
            $install openvswitch-datapath-dkms
        fi
	if $install openvswitch-switch openvswitch-controller; then
            echo "Ignoring error installing openvswitch-controller"
        fi
        ovspresent=1
    fi

    # Switch can run on its own, but
    # Mininet should control the controller
    if [ -e /etc/init.d/openvswitch-controller ]; then
        if sudo service openvswitch-controller stop; then
            echo "Stopped running controller"
        fi
        sudo update-rc.d openvswitch-controller disable
    fi

    if [ $ovspresent = 1 ]; then
        echo "Done (hopefully) installing packages"
        cd $BUILD_DIR
        return
    fi

    # Otherwise attempt to install from source

    $install pkg-config gcc make python-dev libssl-dev libtool

    if [ "$DIST" = "Debian" ]; then
        if [ "$CODENAME" = "lenny" ]; then
            $install git-core
            # Install Autoconf 2.63+ backport from Debian Backports repo:
            # Instructions from http://backports.org/dokuwiki/doku.php?id=instructions
            sudo su -c "echo 'deb http://www.backports.org/debian lenny-backports main contrib non-free' >> /etc/apt/sources.list"
            sudo apt-get update
            sudo apt-get -y --force-yes install debian-backports-keyring
            sudo apt-get -y --force-yes -t lenny-backports install autoconf
        fi
    else
        $install git
    fi

    # Install OVS from release
    cd $BUILD_DIR/
    git clone git://openvswitch.org/openvswitch $OVS_SRC
    cd $OVS_SRC
    git checkout $OVS_TAG
    ./boot.sh
    BUILDDIR=/lib/modules/${KERNEL_NAME}/build
    if [ ! -e $BUILDDIR ]; then
        echo "Creating build sdirectory $BUILDDIR"
        sudo mkdir -p $BUILDDIR
    fi
    opts="--with-linux=$BUILDDIR"
    mkdir -p $OVS_BUILD
    cd $OVS_BUILD
    ../configure $opts
    make
    sudo make install

    modprobe
}

function remove_ovs {
    pkgs=`dpkg --get-selections | grep openvswitch | awk '{ print $1;}'`
    echo "Removing existing Open vSwitch packages:"
    echo $pkgs
    if ! $remove $pkgs; then
        echo "Not all packages removed correctly"
    fi
    # For some reason this doesn't happen
    if scripts=`ls /etc/init.d/*openvswitch* 2>/dev/null`; then
        echo $scripts
        for s in $scripts; do
            s=$(basename $s)
            echo SCRIPT $s
            sudo service $s stop
            sudo rm -f /etc/init.d/$s
            sudo update-rc.d -f $s remove
        done
    fi
    echo "Done removing OVS"
}

function ivs {
    echo "Installing Indigo Virtual Switch..."

    IVS_SRC=$BUILD_DIR/ivs

    # Install dependencies
    $install git pkg-config gcc make libnl-3-dev libnl-route-3-dev libnl-genl-3-dev

    # Install IVS from source
    cd $BUILD_DIR
    git clone git://github.com/floodlight/ivs $IVS_SRC -b $IVS_TAG --recursive
    cd $IVS_SRC
    make
    sudo make install
}

# Install NOX with tutorial files
function nox {
    echo "Installing NOX w/tutorial files..."

    # Install NOX deps:
    $install autoconf automake g++ libtool python python-twisted \
		swig libssl-dev make
    if [ "$DIST" = "Debian" ]; then
        $install libboost1.35-dev
    elif [ "$DIST" = "Ubuntu" ]; then
        $install python-dev libboost-dev
        $install libboost-filesystem-dev
        $install libboost-test-dev
    fi
    # Install NOX optional deps:
    $install libsqlite3-dev python-simplejson

    # Fetch NOX destiny
    cd $BUILD_DIR/
    git clone https://github.com/noxrepo/nox-classic.git noxcore
    cd noxcore
    if ! git checkout -b destiny remotes/origin/destiny ; then
        echo "Did not check out a new destiny branch - assuming current branch is destiny"
    fi

    # Apply patches
    git checkout -b tutorial-destiny
    git am $MININET_DIR/mininet/util/nox-patches/*tutorial-port-nox-destiny*.patch
    if [ "$DIST" = "Ubuntu" ] && [ `expr $RELEASE '>=' 12.04` = 1 ]; then
        git am $MININET_DIR/mininet/util/nox-patches/*nox-ubuntu12-hacks.patch
    fi

    # Build
    ./boot.sh
    mkdir build
    cd build
    ../configure
    make -j3
    #make check

    # Add NOX_CORE_DIR env var:
    sed -i -e 's|# for examples$|&\nexport NOX_CORE_DIR=$BUILD_DIR/noxcore/build/src|' ~/.bashrc

    # To verify this install:
    #cd ~/noxcore/build/src
    #./nox_core -v -i ptcp:
}

# Install NOX Classic/Zaku for OpenFlow 1.3
function nox13 {
    echo "Installing NOX w/tutorial files..."

    # Install NOX deps:
    $install autoconf automake g++ libtool python python-twisted \
        swig libssl-dev make
    if [ "$DIST" = "Debian" ]; then
        $install libboost1.35-dev
    elif [ "$DIST" = "Ubuntu" ]; then
        $install python-dev libboost-dev
        $install libboost-filesystem-dev
        $install libboost-test-dev
    fi

    # Fetch NOX destiny
    cd $BUILD_DIR/
    git clone https://github.com/CPqD/nox13oflib.git
    cd nox13oflib

    # Build
    ./boot.sh
    mkdir build
    cd build
    ../configure
    make -j3
    #make check

    # To verify this install:
    #cd ~/nox13oflib/build/src
    #./nox_core -v -i ptcp:
}


# "Install" POX
function pox {
    echo "Installing POX into $BUILD_DIR/pox..."
    cd $BUILD_DIR
    git clone https://github.com/noxrepo/pox.git
}

# Install OFtest
function oftest {
    echo "Installing oftest..."

    # Install deps:
    $install tcpdump python-scapy

    # Install oftest:
    cd $BUILD_DIR/
    git clone git://github.com/floodlight/oftest
}

# Install cbench
function cbench {
    echo "Installing cbench..."

    $install libsnmp-dev libpcap-dev libconfig-dev
    cd $BUILD_DIR/
    git clone git://openflow.org/oflops.git
    cd oflops
    sh boot.sh || true # possible error in autoreconf, so run twice
    sh boot.sh
    ./configure --with-openflow-src-dir=$BUILD_DIR/openflow
    make
    sudo make install || true # make install fails; force past this
}

function vm_other {
    echo "Doing other Mininet VM setup tasks..."

    # Remove avahi-daemon, which may cause unwanted discovery packets to be
    # sent during tests, near link status changes:
    echo "Removing avahi-daemon"
    $remove avahi-daemon

    # was: Disable IPv6.  Add to /etc/modprobe.d/blacklist:
    #echo "Attempting to disable IPv6"
    #if [ "$DIST" = "Ubuntu" ]; then
    #    BLACKLIST=/etc/modprobe.d/blacklist.conf
    #else
    #    BLACKLIST=/etc/modprobe.d/blacklist
    #fi
    #sudo sh -c "echo 'blacklist net-pf-10\nblacklist ipv6' >> $BLACKLIST"

    # Disable IPv6
    if ! grep 'disable IPv6' /etc/sysctl.conf; then
        echo 'Disabling IPv6'
        echo '
# Mininet: disable IPv6
net.ipv6.conf.all.disable_ipv6 = 1
net.ipv6.conf.default.disable_ipv6 = 1
net.ipv6.conf.lo.disable_ipv6 = 1' | sudo tee -a /etc/sysctl.conf > /dev/null
    fi
    # Disabling IPv6 breaks X11 forwarding via ssh
    line='AddressFamily inet'
    file='/etc/ssh/sshd_config'
    echo "Adding $line to $file"
    if ! grep "$line" $file > /dev/null; then
        echo "$line" | sudo tee -a $file > /dev/null
    fi

    # Enable command auto completion using sudo; modify ~/.bashrc:
    sed -i -e 's|# for examples$|&\ncomplete -cf sudo|' ~/.bashrc

    # Install tcpdump, cmd-line packet dump tool.  Also install gitk,
    # a graphical git history viewer.
    $install tcpdump gitk

    # Install common text editors
    $install vim nano emacs

    # Install NTP
    $install ntp

    # Set git to colorize everything.
    git config --global color.diff auto
    git config --global color.status auto
    git config --global color.branch auto

    # Reduce boot screen opt-out delay. Modify timeout in /boot/grub/menu.lst to 1:
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
    set +o nounset
    if [ -z "$OVS_KMODS" ]; then
      echo "OVS_KMODS not set. Aborting."
    else
      sudo cp $OVS_KMODS $DRIVERS_DIR
      sudo depmod -a ${KERNEL_NAME}
    fi
    set -o nounset
}

function all {
    echo "Running all commands..."
    kernel
    mn_deps
    mn_dev
    of
    wireshark
    ovs
    # NOX-classic is deprecated, but you can install it manually if desired.
    # nox
    pox
    oftest
    cbench
    echo "Enjoy Mininet!"
}

# Restore disk space and remove sensitive files before shipping a VM.
function vm_clean {
    echo "Cleaning VM..."
    sudo apt-get clean
    sudo apt-get autoremove
    sudo rm -rf /tmp/*
    sudo rm -rf openvswitch*.tar.gz

    # Remove sensistive files
    history -c  # note this won't work if you have multiple bash sessions
    rm -f ~/.bash_history  # need to clear in memory and remove on disk
    rm -f ~/.ssh/id_rsa* ~/.ssh/known_hosts
    sudo rm -f ~/.ssh/authorized_keys*

    # Remove Mininet files
    #sudo rm -f /lib/modules/python2.5/site-packages/mininet*
    #sudo rm -f /usr/bin/mnexec

    # Clear optional dev script for SSH keychain load on boot
    rm -f ~/.bash_profile

    # Clear git changes
    git config --global user.name "None"
    git config --global user.email "None"

    # Note: you can shrink the .vmdk in vmware using
    # vmware-vdiskmanager -k *.vmdk
    echo "Zeroing out disk blocks for efficient compaction..."
    time sudo dd if=/dev/zero of=/tmp/zero bs=1M
    sync ; sleep 1 ; sync ; sudo rm -f /tmp/zero

}

function usage {
    printf '\nUsage: %s [-abcdfhikmnprtvwx03]\n\n' $(basename $0) >&2

    printf 'This install script attempts to install useful packages\n' >&2
    printf 'for Mininet. It should (hopefully) work on Ubuntu 11.10+\n' >&2
    printf 'If you run into trouble, try\n' >&2
    printf 'installing one thing at a time, and looking at the \n' >&2
    printf 'specific installation function in this script.\n\n' >&2

    printf 'options:\n' >&2
    printf -- ' -a: (default) install (A)ll packages - good luck!\n' >&2
    printf -- ' -b: install controller (B)enchmark (oflops)\n' >&2
    printf -- ' -c: (C)lean up after kernel install\n' >&2
    printf -- ' -d: (D)elete some sensitive files from a VM image\n' >&2
    printf -- ' -e: install Mininet d(E)veloper dependencies\n' >&2
    printf -- ' -f: install Open(F)low\n' >&2
    printf -- ' -h: print this (H)elp message\n' >&2
    printf -- ' -i: install (I)ndigo Virtual Switch\n' >&2
    printf -- ' -k: install new (K)ernel\n' >&2
    printf -- ' -m: install Open vSwitch kernel (M)odule from source dir\n' >&2
    printf -- ' -n: install Mini(N)et dependencies + core files\n' >&2
    printf -- ' -p: install (P)OX OpenFlow Controller\n' >&2
    printf -- ' -r: remove existing Open vSwitch packages\n' >&2
    printf -- ' -s <dir>: place dependency (S)ource/build trees in <dir>\n' >&2
    printf -- ' -t: complete o(T)her Mininet VM setup tasks\n' >&2
    printf -- ' -v: install Open (V)switch\n' >&2
    printf -- ' -w: install OpenFlow (W)ireshark dissector\n' >&2
    printf -- ' -x: install NO(X) Classic OpenFlow controller\n' >&2
    printf -- ' -0: (default) -0[fx] installs OpenFlow 1.0 versions\n' >&2
    printf -- ' -3: -3[fx] installs OpenFlow 1.3 versions\n' >&2
    exit 2
}

OF_VERSION=1.0

if [ $# -eq 0 ]
then
    all
else
    while getopts 'abcdefhikmnprs:tvwx03' OPTION
    do
      case $OPTION in
      a)    all;;
      b)    cbench;;
      c)    kernel_clean;;
      d)    vm_clean;;
      e)    mn_dev;;
      f)    case $OF_VERSION in
            1.0) of;;
            1.3) of13;;
            *)  echo "Invalid OpenFlow version $OF_VERSION";;
            esac;;
      h)    usage;;
      i)    ivs;;
      k)    kernel;;
      m)    modprobe;;
      n)    mn_deps;;
      p)    pox;;
      r)    remove_ovs;;
      s)    mkdir -p $OPTARG; # ensure the directory is created
            BUILD_DIR="$( cd -P "$OPTARG" && pwd )"; # get the full path
            echo "Dependency installation directory: $BUILD_DIR";;
      t)    vm_other;;
      v)    ovs;;
      w)    wireshark;;
      x)    case $OF_VERSION in
            1.0) nox;;
            1.3) nox13;;
            *)  echo "Invalid OpenFlow version $OF_VERSION";;
            esac;;
      0)    OF_VERSION=1.0;;
      3)    OF_VERSION=1.3;;
      ?)    usage;;
      esac
    done
    shift $(($OPTIND - 1))
fi
