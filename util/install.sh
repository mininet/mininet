#!/bin/bash

# Mininet install script for Ubuntu and Debian
# Original author: Brandon Heller

# Fail on error
set -e

# Fail on unset var usage
set -o nounset

# Get directory containing mininet folder
MININET_DIR="$( cd -P "$( dirname "${BASH_SOURCE[0]}" )/../.." && pwd -P )"

# Set up build directory, which by default is the working directory
#  unless the working directory is a subdirectory of mininet,
#  in which case we use the directory containing mininet
BUILD_DIR="$(pwd -P)"
case $BUILD_DIR in
  $MININET_DIR/*) BUILD_DIR=$MININET_DIR;; # current directory is a subdirectory
  *) BUILD_DIR=$BUILD_DIR;;
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
    # Truly non-interactive apt-get installation
    install='sudo DEBIAN_FRONTEND=noninteractive apt-get -y -q install'
    remove='sudo DEBIAN_FRONTEND=noninteractive apt-get -y -q remove'
    pkginst='sudo dpkg -i'
    update='sudo apt-get'
    # Prereqs for this script
    if ! which lsb_release &> /dev/null; then
        $install lsb-release
    fi
fi
test -e /etc/fedora-release && DIST="Fedora"
test -e /etc/redhat-release && DIST="RedHatEnterpriseServer"
if [ "$DIST" = "Fedora" -o "$DIST" = "RedHatEnterpriseServer" ]; then
    install='sudo yum -y install'
    remove='sudo yum -y erase'
    pkginst='sudo rpm -ivh'
    update='sudo yum'
    # Prereqs for this script
    if ! which lsb_release &> /dev/null; then
        $install redhat-lsb-core
    fi
fi
test -e /etc/SuSE-release && DIST="SUSE Linux"
if [ "$DIST" = "SUSE Linux" ]; then
    install='sudo zypper --non-interactive install '
    remove='sudo zypper --non-interactive  remove '
    pkginst='sudo rpm -ivh'
    # Prereqs for this script
    if ! which lsb_release &> /dev/null; then
		$install openSUSE-release
    fi
fi
if which lsb_release &> /dev/null; then
    DIST=`lsb_release -is`
    RELEASE=`lsb_release -rs`
    CODENAME=`lsb_release -cs`
fi
echo "Detected Linux distribution: $DIST $RELEASE $CODENAME $ARCH"

# Kernel params

KERNEL_NAME=`uname -r`
KERNEL_HEADERS=kernel-headers-${KERNEL_NAME}

# Treat Raspbian as Debian
[ "$DIST" = 'Raspbian' ] && DIST='Debian'

DISTS='Ubuntu|Debian|Fedora|RedHatEnterpriseServer|SUSE LINUX'
if ! echo $DIST | egrep "$DISTS" >/dev/null; then
    echo "Install.sh currently only supports $DISTS."
    exit 1
fi

# More distribution info
DIST_LC=`echo $DIST | tr [A-Z] [a-z]` # as lower case


# Determine whether version $1 >= version $2
# usage: if version_ge 1.20 1.2.3; then echo "true!"; fi
function version_ge {
    # sort -V sorts by *version number*
    latest=`printf "$1\n$2" | sort -V | tail -1`
    # If $1 is latest version, then $1 >= $2
    [ "$1" == "$latest" ]
}

# Attempt to detect Python version
PYTHON=${PYTHON:-python}
PRINTVERSION='import sys; print(sys.version_info)'
PYTHON_VERSION=unknown
for python in $PYTHON python2 python3; do
    if $python -c "$PRINTVERSION" |& grep 'major=2'; then
        PYTHON=$python; PYTHON_VERSION=2; PYPKG=python
        break
    elif $python -c "$PRINTVERSION" |& grep 'major=3'; then
        PYTHON=$python; PYTHON_VERSION=3; PYPKG=python3
        break
    fi
done
if [ "$PYTHON_VERSION" == unknown ]; then
    echo "Can't find a working python command ('$PYTHON' doesn't work.)"
    echo "You may wish to export PYTHON or install a working 'python'."
    exit 1
fi

echo "Detected Python (${PYTHON}) version ${PYTHON_VERSION}"

# Kernel Deb pkg to be removed:
KERNEL_IMAGE_OLD=linux-image-2.6.26-33-generic

DRIVERS_DIR=/lib/modules/${KERNEL_NAME}/kernel/drivers/net

OVS_RELEASE=1.4.0
OVS_PACKAGE_LOC=https://github.com/downloads/mininet/mininet
OVS_BUILDSUFFIX=-ignore # was -2
OVS_PACKAGE_NAME=ovs-$OVS_RELEASE-core-$DIST_LC-$RELEASE-$ARCH$OVS_BUILDSUFFIX.tar
OVS_TAG=v$OVS_RELEASE

OF13_SWITCH_REV=${OF13_SWITCH_REV:-""}


function kernel {
    echo "Install Mininet-compatible kernel if necessary"
    $update update
    if ! $install linux-image-$KERNEL_NAME; then
        echo "Could not install linux-image-$KERNEL_NAME"
        echo "Skipping - assuming installed kernel is OK."
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
    if [ "$DIST" = "Fedora" -o "$DIST" = "RedHatEnterpriseServer" ]; then
        $install gcc make socat psmisc xterm openssh-clients iperf \
            iproute telnet python-setuptools libcgroup-tools \
            ethtool help2man net-tools
        $install ${PYPKG}-pyflakes pylint ${PYPKG}-pep8-naming \
            ${PYPKG}-pexpect
    elif [ "$DIST" = "SUSE LINUX"  ]; then
		$install gcc make socat psmisc xterm openssh iperf \
			iproute telnet ${PYPKG}-setuptools libcgroup-tools \
			ethtool help2man python-pyflakes python3-pylint \
                        python-pep8 ${PYPKG}-pexpect ${PYPKG}-tk
    else  # Debian/Ubuntu
        pf=pyflakes
        pep8=pep8
        # Starting around 20.04, installing pyflakes instead of pyflakes3
        # causes Python 2 to be installed, which is exactly NOT what we want.
        if [ "$DIST" = "Ubuntu" -a `expr $RELEASE '>=' 20.04` = "1" ]; then
                pf=pyflakes3
        fi
        # Debian 11 "bullseye" renamed
        # * pep8 to python3-pep8
        # * pyflakes to pyflakes3
        if [ "$DIST" = "Debian" -a `expr $RELEASE '>=' 11` = "1" ]; then
                pf=pyflakes3
                pep8=python3-pep8
        fi

        $install gcc make socat psmisc xterm ssh iperf telnet \
                 ethtool help2man $pf pylint $pep8 \
                 net-tools ${PYPKG}-tk

        # Install pip
        $install ${PYPKG}-pip || $install ${PYPKG}-pip-whl
        if ! ${PYTHON} -m pip -V; then
            if [ $PYTHON_VERSION == 2 ]; then
                wget https://bootstrap.pypa.io/pip/2.7/get-pip.py
            else
                wget https://bootstrap.pypa.io/get-pip.py
            fi
            sudo ${PYTHON} get-pip.py
            rm get-pip.py
        fi
       ${python} -m pip install pexpect
        $install iproute2 || $install iproute
        $install cgroup-tools || $install cgroup-bin
        $install cgroupfs-mount
    fi

    echo "Installing Mininet core"
    pushd $MININET_DIR/mininet
    sudo PYTHON=${PYTHON} make install
    popd
}

# Install Mininet documentation dependencies
function mn_doc {
    echo "Installing Mininet documentation dependencies"
    $install doxygen texlive-fonts-recommended
    if ! $install doxygen-latex; then
        echo "doxygen-latex not needed"
    fi
    sudo pip2 install doxypy
}

# The following will cause a full OF install, covering:
# -user switch
# The instructions below are an abbreviated version from
# http://www.openflowswitch.org/wk/index.php/Debian_Install
function of {
    echo "Installing OpenFlow reference implementation..."
    cd $BUILD_DIR
    $install autoconf automake libtool make gcc
    if [ "$DIST" = "Fedora" -o "$DIST" = "RedHatEnterpriseServer" ]; then
        $install git pkgconfig glibc-devel
	elif [ "$DIST" = "SUSE LINUX"  ]; then
       $install git pkgconfig glibc-devel
    else
        $install git-core autotools-dev pkg-config libc6-dev
    fi
    # was: git clone git://openflowswitch.org/openflow.git
    # Use our own fork on github for now:
    git clone https://github.com/mininet/openflow
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
    $install git-core autoconf automake autotools-dev pkg-config \
        make gcc g++ libtool libc6-dev cmake libpcap-dev  \
        unzip libpcre3-dev flex bison libboost-dev
    if [ "$DIST" = "Ubuntu" ] && version_le $RELEASE 16.04; then
        $install libxerces-c2-dev
    else
        $install libxerces-c-dev
    fi
    if [ ! -d "ofsoftswitch13" ]; then
        git clone https://github.com/CPqD/ofsoftswitch13.git
        if [[ -n "$OF13_SWITCH_REV" ]]; then
            cd ofsoftswitch13
            git checkout ${OF13_SWITCH_REV}
            cd ..
        fi
    fi

    # Install netbee
    if [ ! -d "netbee" ]; then
        git clone https://github.com/netgroup-polito/netbee.git
    fi
    cd netbee/src
    cmake .
    make

    cd $BUILD_DIR
    sudo cp netbee/bin/libn*.so /usr/local/lib
    sudo ldconfig
    sudo cp -R netbee/include/ /usr/

    # Resume the install:
    cd $BUILD_DIR/ofsoftswitch13
    ./boot.sh
    ./configure
    make
    sudo make install
    cd $BUILD_DIR
}


function install_wireshark {
    if ! which wireshark; then
        echo "Installing Wireshark"
        if [ "$DIST" = "Fedora" -o "$DIST" = "RedHatEnterpriseServer" ]; then
            $install wireshark wireshark-gnome
		elif [ "$DIST" = "SUSE LINUX"  ]; then
			$install wireshark
        else
            $install wireshark tshark
        fi
    fi

    # Copy coloring rules: OF is white-on-blue:
    echo "Optionally installing wireshark color filters"
    mkdir -p $HOME/.wireshark
    cp -n $MININET_DIR/mininet/util/colorfilters $HOME/.wireshark

    echo "Checking Wireshark version"
    WSVER=`wireshark -v | egrep -o '[0-9\.]+' | head -1`
    if version_ge $WSVER 1.12; then
        echo "Wireshark version $WSVER >= 1.12 - returning"
        return
    fi

    echo "Cloning LoxiGen and building openflow.lua dissector"
    cd $BUILD_DIR
    git clone https://github.com/floodlight/loxigen.git
    cd loxigen
    make wireshark

    # Copy into plugin directory
    # libwireshark0/ on 11.04; libwireshark1/ on later
    WSDIR=`find /usr/lib -type d -name 'libwireshark*' | head -1`
    WSPLUGDIR=$WSDIR/plugins/
    PLUGIN=loxi_output/wireshark/openflow.lua
    sudo cp $PLUGIN $WSPLUGDIR
    echo "Copied openflow plugin $PLUGIN to $WSPLUGDIR"

    cd $BUILD_DIR
}


# Install Open vSwitch specific version Ubuntu package
function ubuntuOvs {
    echo "Creating and Installing Open vSwitch packages..."

    OVS_SRC=$BUILD_DIR/openvswitch
    OVS_TARBALL_LOC=http://openvswitch.org/releases

    if ! echo "$DIST" | egrep "Ubuntu|Debian" > /dev/null; then
        echo "OS must be Ubuntu or Debian"
        $cd BUILD_DIR
        return
    fi
    if [ "$DIST" = "Ubuntu" ] && ! version_ge $RELEASE 12.04; then
        echo "Ubuntu version must be >= 12.04"
        cd $BUILD_DIR
        return
    fi
    if [ "$DIST" = "Debian" ] && ! version_ge $RELEASE 7.0; then
        echo "Debian version must be >= 7.0"
        cd $BUILD_DIR
        return
    fi

    rm -rf $OVS_SRC
    mkdir -p $OVS_SRC
    cd $OVS_SRC

    if wget $OVS_TARBALL_LOC/openvswitch-$OVS_RELEASE.tar.gz 2> /dev/null; then
        tar xzf openvswitch-$OVS_RELEASE.tar.gz
    else
        echo "Failed to find OVS at $OVS_TARBALL_LOC/openvswitch-$OVS_RELEASE.tar.gz"
        cd $BUILD_DIR
        return
    fi

    # Remove any old packages

    $remove openvswitch-common openvswitch-datapath-dkms openvswitch-pki openvswitch-switch \
            openvswitch-controller || true

    # Get build deps
    $install build-essential fakeroot debhelper autoconf automake libssl-dev \
             pkg-config bzip2 openssl ${PYPKG}-all procps ${PYPKG}-qt4 \
             ${PYPKG}-zopeinterface ${PYPKG}-twisted-conch dkms dh-python dh-autoreconf \
             uuid-runtime

    # Build OVS
    parallel=`grep processor /proc/cpuinfo | wc -l`
    cd $BUILD_DIR/openvswitch/openvswitch-$OVS_RELEASE
            DEB_BUILD_OPTIONS='parallel=$parallel nocheck' fakeroot debian/rules binary
    cd ..
    for pkg in common datapath-dkms pki switch; do
        pkg=openvswitch-${pkg}_$OVS_RELEASE*.deb
        echo "Installing $pkg"
        $pkginst $pkg
    done
    if $pkginst openvswitch-controller_$OVS_RELEASE*.deb 2>/dev/null; then
        echo "Ignoring error installing openvswitch-controller"
    fi

    /sbin/modinfo openvswitch
    sudo ovs-vsctl show
    # Switch can run on its own, but
    # Mininet should control the controller
    # This appears to only be an issue on Ubuntu/Debian
    if sudo service openvswitch-controller stop 2>/dev/null; then
        echo "Stopped running controller"
    fi
    if [ -e /etc/init.d/openvswitch-controller ]; then
        sudo update-rc.d openvswitch-controller disable
    fi
}


# Install Open vSwitch

function ovs {
    echo "Installing Open vSwitch..."

    if [ "$DIST" = "Fedora" -o "$DIST" = "RedHatEnterpriseServer" ]; then
        $install openvswitch
        if ! $install openvswitch-controller; then
            echo "openvswitch-controller not installed"
        fi
        return
    fi

    if [ "$DIST" = "Ubuntu" ] && ! version_ge $RELEASE 14.04; then
        # Older Ubuntu versions need openvswitch-datapath/-dkms
        # Manually installing openvswitch-datapath may be necessary
        # for manually built kernel .debs using Debian's defective kernel
        # packaging, which doesn't yield usable headers.
        if ! dpkg --get-selections | grep openvswitch-datapath; then
            # If you've already installed a datapath, assume you
            # know what you're doing and don't need dkms datapath.
            # Otherwise, install it.
            $install openvswitch-datapath-dkms
        fi
    fi

    $install openvswitch-switch
    OVSC=""
    if $install openvswitch-controller; then
        OVSC="openvswitch-controller"
    else
        echo "Attempting to install openvswitch-testcontroller"
        if $install openvswitch-testcontroller; then
            OVSC="openvswitch-testcontroller"
        else
            echo "Failed - skipping openvswitch-testcontroller"
        fi
    fi
    if [ "$OVSC" ]; then
        # Switch can run on its own, but
        # Mininet should control the controller
        # This appears to only be an issue on Ubuntu/Debian
        if sudo service $OVSC stop 2>/dev/null; then
            echo "Stopped running controller"
        fi
        if [ -e /etc/init.d/$OVSC ]; then
            sudo update-rc.d $OVSC disable
        fi
    fi
    # This service seems to hang on 20.04
    if systemctl list-units | \
            grep status netplan-ovs-cleanup.service>&/dev/null; then
        echo 'TimeoutSec=10' | sudo EDITOR='tee -a' \
        sudo systemctl edit --full netplan-ovs-cleanup.service
    fi
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
    $install gcc make
    if [ "$DIST" = "Fedora" -o "$DIST" = "RedHatEnterpriseServer" ]; then
        $install git pkgconfig libnl3-devel libcap-devel openssl-devel
    else
        $install git-core pkg-config libnl-3-dev libnl-route-3-dev \
            libnl-genl-3-dev
    fi

    # Install IVS from source
    cd $BUILD_DIR
    git clone https://github.com/floodlight/ivs $IVS_SRC
    cd $IVS_SRC
    git submodule update --init
    make
    sudo make install
}

# Install RYU
function ryu {
    echo "Installing RYU..."

    # install Ryu dependencies"
    $install autoconf automake g++ libtool python make
    if [ "$DIST" = "Ubuntu" -o "$DIST" = "Debian" ]; then
        $install gcc ${PYPKG}-pip ${PYPKG}-dev libffi-dev libssl-dev \
            libxml2-dev libxslt1-dev zlib1g-dev
    fi

    # fetch RYU
    cd $BUILD_DIR/
    git clone https://github.com/osrg/ryu.git ryu
    cd ryu

    # install ryu
    sudo pip install -r tools/pip-requires -r tools/optional-requires \
        -r tools/test-requires
    sudo python setup.py install

    # Add symbolic link to /usr/bin
    sudo ln -s ./bin/ryu-manager /usr/local/bin/ryu-manager
}

# Install NOX with tutorial files
function nox {
    echo "Installing NOX w/tutorial files..."

    # Install NOX deps:
    $install autoconf automake g++ libtool python ${PYPKG}-twisted \
		swig libssl-dev make
    if [ "$DIST" = "Debian" ]; then
        $install libboost1.35-dev
    elif [ "$DIST" = "Ubuntu" ]; then
        $install ${PYPKG}-dev libboost-dev
        $install libboost-filesystem-dev
        $install libboost-test-dev
    fi
    # Install NOX optional deps:
    $install libsqlite3-dev ${PYPKG}-simplejson

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
    if [ "$DIST" = "Ubuntu" ] && version_ge $RELEASE 12.04; then
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
    $install autoconf automake g++ libtool python ${PYPKG}-twisted \
        swig libssl-dev make
    if [ "$DIST" = "Debian" ]; then
        $install libboost1.35-dev
    elif [ "$DIST" = "Ubuntu" ]; then
        $install ${PYPKG}-dev libboost-dev
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
    $install tcpdump
    $install ${PYPKG}-scapy || sudo $PYTHON -m pip install scapy

    # Install oftest:
    cd $BUILD_DIR/
    git clone https://github.com/floodlight/oftest
}

# Install cbench
function cbench {
    echo "Installing cbench..."

    if [ "$DIST" = "Fedora" -o "$DIST" = "RedHatEnterpriseServer" ]; then
        $install net-snmp-devel libpcap-devel libconfig-devel
	elif [ "$DIST" = "SUSE LINUX"  ]; then
		$install net-snmp-devel libpcap-devel libconfig-devel
    else
        $install libsnmp-dev libpcap-dev libconfig-dev
    fi
    cd $BUILD_DIR/
    # was:  git clone git://gitosis.stanford.edu/oflops.git
    # Use our own fork on github for now:
    git clone https://github.com/mininet/oflops
    cd oflops
    sh boot.sh || true # possible error in autoreconf, so run twice
    sh boot.sh
    ./configure --with-openflow-src-dir=$BUILD_DIR/openflow
    make liboflops_test.la
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
    echo "Disabling IPv6"
    # Disable IPv6
    if ! grep 'disable_ipv6' /etc/sysctl.conf; then
        echo 'Disabling IPv6'
        echo '
# Mininet: disable IPv6
net.ipv6.conf.all.disable_ipv6 = 1
net.ipv6.conf.default.disable_ipv6 = 1
net.ipv6.conf.lo.disable_ipv6 = 1' | sudo tee -a /etc/sysctl.conf > /dev/null
    fi
    # Since the above doesn't disable neighbor discovery, also do this:
    # disable via boot line, and also restore eth0 naming for VM use
    if ! grep 'ipv6.disable' /etc/default/grub; then
        sudo sed -i -e \
        's/GRUB_CMDLINE_LINUX_DEFAULT="/GRUB_CMDLINE_LINUX_DEFAULT="ipv6.disable=1 net.ifnames=0 /' \
        /etc/default/grub
        sudo update-grub
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

    # Install vconfig for VLAN example
    if [ "$DIST" = "Fedora" -o "$DIST" = "RedHatEnterpriseServer" ]; then
        $install vconfig
    else
        $install vlan
    fi

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
    if [ "$DIST" = "Fedora" ]; then
        printf "\nFedora 18+ support (still work in progress):\n"
        printf " * Fedora 18+ has kernel 3.10 RPMS in the updates repositories\n"
        printf " * Fedora 18+ has openvswitch 1.10 RPMS in the updates repositories\n"
        printf " * the install.sh script options [-bfnpvw] should work.\n"
        printf " * for a basic setup just try:\n"
        printf "       install.sh -fnpv\n\n"
        exit 3
    fi
    echo "Installing all packages except for -eix (doxypy, ivs, nox-classic)..."
    kernel
    mn_deps
    # Skip mn_doc (doxypy/texlive/fonts/etc.) because it's huge
    # mn_doc
    of
    install_wireshark
    ovs
    # We may add ivs once it's more mature
    # ivs
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

    # Remove sensitive files
    history -c  # note this won't work if you have multiple bash sessions
    rm -f ~/.bash_history  # need to clear in memory and remove on disk
    rm -f ~/.ssh/id_rsa* ~/.ssh/known_hosts
    sudo rm -f ~/.ssh/authorized_keys*

    # Remove SSH keys and regenerate on boot
    echo 'Removing SSH keys from /etc/ssh/'
    sudo rm -f /etc/ssh/*key*
    if [ ! -e /etc/rc.local ]; then
        echo '#!/bin/bash' | sudo tee /etc/rc.local
        sudo chmod +x /etc/rc.local
    fi
    if ! grep mininet /etc/rc.local >& /dev/null; then
        sudo sed -i -e "s/exit 0//" /etc/rc.local || true
        echo '
# mininet: regenerate ssh keys if we deleted them
if ! stat -t /etc/ssh/*key* >/dev/null 2>&1; then
    /usr/sbin/dpkg-reconfigure openssh-server
fi
exit 0
' | sudo tee -a /etc/rc.local > /dev/null
        sudo chmod +x /etc/rc.local
    fi

    # Clear optional dev script for SSH keychain load on boot
    rm -f ~/.bash_profile

    # Remove leftover install script if any
    rm -f install-mininet-vm.sh

    # Clear git changes
    git config --global user.name "None"
    git config --global user.email "None"

    # Note: you can shrink the .vmdk in vmware using
    # vmware-vdiskmanager -k *.vmdk
    echo "Zeroing out disk blocks for efficient compaction..."
    time sudo dd if=/dev/zero of=/tmp/zero bs=1M || true
    sync ; sleep 1 ; sync ; sudo rm -f /tmp/zero

}

function usage {
    printf '\nUsage: %s [-abcdefhikmnprtvVwxy03]\n\n' $(basename $0) >&2

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
    printf -- ' -e: install Mininet documentation/LaT(e)X dependencies\n' >&2
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
    printf -- ' -V <version>: install a particular version of Open (V)switch on Ubuntu\n' >&2
    printf -- ' -w: install OpenFlow (W)ireshark dissector\n' >&2
    printf -- ' -x: install NO(X) Classic OpenFlow controller\n' >&2    
    printf -- ' -y: install R(y)u Controller\n' >&2
    printf -- ' -0: (default) -0[fx] installs OpenFlow 1.0 versions\n' >&2
    printf -- ' -3: -3[fx] installs OpenFlow 1.3 versions\n' >&2
    exit 2
}

OF_VERSION=1.0

if [ $# -eq 0 ]
then
    all
else
    while getopts 'abcdefhikmnprs:tvV:wxy03' OPTION
    do
      case $OPTION in
      a)    all;;
      b)    cbench;;
      c)    kernel_clean;;
      d)    vm_clean;;
      e)    mn_doc;;
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
      V)    OVS_RELEASE=$OPTARG;
            ubuntuOvs;;
      w)    install_wireshark;;
      x)    case $OF_VERSION in
            1.0) nox;;
            1.3) nox13;;
            *)  echo "Invalid OpenFlow version $OF_VERSION";;
            esac;;
      y)    ryu;;
      0)    OF_VERSION=1.0;;
      3)    OF_VERSION=1.3;;
      ?)    usage;;
      esac
    done
    shift $(($OPTIND - 1))
fi
