#!/bin/bash
# Builds kernel with the new CFS Bandwidth patches
# and nsfd/setns syscall patches.
# Also builds Open vSwitch against the built kernel version.
# Script only to be run on 64-bit systems; needs a few changes to run on
# 32-bit ones.

# If building for i386 (-t), make sure to install the following 32-bit libs:
# sudo apt-get install ia32-libs lib32gcc1 libc6-i386 util-linux devscripts

# Check for unitialized variables
set -o nounset

# Exit on any failure
set -e

# Location in which to download and build the kernel
kdir=/usr/src

# Kernel version to download
kver=3.0.0

# Save original directory for later.
orig_dir=`pwd`

# Default and custom kernel version string
version_string=-with-cfs

# Run menuconfig later?
menuconfig=

# Use localmodconfig?
localmodconfig=

# Build ubuntu kernel? must be 3.0.0 compatible
ubuntu_release=
ubuntu_default_release=ubuntu-oneiric
ubuntu_base=3.0.0-14  # base tag and version for build
ubuntu_tag=Ubuntu-$ubuntu_base.23
ubuntu_flavor=generic
#ubuntu_config=/boot/config-$ubuntu_base-$ubuntu_flavor
ubuntu_config=${orig_dir}/config-3.0.9-with-cfs
ubuntu_image=linux-image-$ubuntu_base-$ubuntu_flavor
ubuntu_kver=3.0.9 # must match version that is actually built

# OVS pkg string.  Not sure how to find this automatically.
ovs_pkg_ver=1.2.0-1ubuntu3

# Location of kernel config.  If not specified, use current .config.
# was: ${orig_dir}/config-3.0.0-with-cfs
kconfig=

# Install only?
install_only=

# Use 32-bit?
i386=

function usage {
    warn "Compiles kernel ${kver} with CBW, setns, and DCTCP patches in ${kdir}"
    warn "Usage: build.sh [-huimlt] [-v 'versionstring']"
    warn "-h help"
    warn "-u build ubuntu kernel"
    warn "-i install only (don't build)"
    warn "-m use menuconfig"
    warn "-l use localmodconfig"
    warn "-v 'versionstring' use custom version string"
    warn "-t build for i386 (32-bit)"
}

function parse_opts {
    custom_version_string=
    plus=
    while getopts 'huimltv:' OPTION; do
        case $OPTION in
            h) usage; exit 0;;
            u) ubuntu_release=$ubuntu_default_release;
		kver=$ubuntu_kver; kconfig=$ubuntu_config;;
	    i) install_only=true;;
	    m) menuconfig=true;;
	    l) localmodconfig=true;;
	    v) custom_version_string=$OPTARG;;
	    t) i386=true; plus=;;
	    ?) usage; exit 1;;
        esac
    done
    # Provide feedback which might be useful
    if [[ "$custom_version_string" != "" ]]; then
        warn "Using custom version_string: ${custom_version_string}"
        version_string=$custom_version_string
    else
        warn "Using default version_string: ${version_string}"
    fi
    if [[ "$ubuntu_release" != "" ]]; then
        warn "Building Ubuntu kernel for release ${ubuntu_release}"
    fi
}

function warn {
    # Echo the provided command in color text.
    yellow='\e[0;33m' # Yellow
    reset='\e[0m'
    echo="echo -e"
    if [ -n "${2+defined}" ]; then
        echo="$echo $2"
    fi
    $echo "${yellow}$1${reset}"
}

function pre_check {
    warn "Checking for git"
    if [[ -z `which git` ]]; then
        warn "You need git to download kernel.  Install? [Y/n] " -n
        read answer
        [[ -z $answer || $answer=="Y" || $answer == "y" ]] && \
            sudo apt-get install git;
    fi

    warn "Checking for kernel-package build utilities"
    if [[ -z `which make-kpkg` ]]; then
        warn "You need kernel-package utilities to build the kernel.  Install? [Y/n] " -n
        read answer
        [[ -z $answer || $answer=="Y" || $answer == "y" ]] && \
            sudo apt-get install kernel-package ncurses-dev;
    fi
}

function fetch_kernel {
    if [[ "$ubuntu_release" == "" ]]; then
    srcdir=$kdir/linux-$kver
    archive=git://git.kernel.org/pub/scm/linux/kernel/git/tip/linux-tip.git
	tag=3.0.0
    else
	warn "Pre-installing $ubuntu_image"
	#sudo apt-get install $ubuntu_image 
	srcdir=$kdir/$ubuntu_release
	archive=git://kernel.ubuntu.com/ubuntu/$ubuntu_release
	tag=$ubuntu_tag
    fi
    if [[ -d $srcdir ]]; then
        warn "Linux source exists in $srcdir, skipping.."
        return
    fi
    warn "--> Fetching kernel $srcdir"
    if git clone $archive $srcdir; then
	return
    fi
    warn "Failed to fetch kernel from $archive"
    if [[ "$ubuntu_release" == "" ]]; then
        warn "Trying github"
	archive=git://github.com/torvalds/linux.git
	if git clone $archive $srcdir; then
	    return
	fi
    fi
    warn "Giving up."
    exit 2
}

function work_around_kernel_package_bug {
    warn "Applying workaround for kernel package bug..."
    # Fix will likely break on any other kernel version, so watch out.
    # From:
    # https://bugs.launchpad.net/ubuntu/+source/kernel-package/+bug/58307/comments/16
    sed -i -s 's/echo "+"/#echo "+"/' $srcdir/scripts/setlocalversion
}

function copy_patches {
    warn "Copying patches..."
    rm -rf $srcdir/patches
    cp -r ${orig_dir}/../../linux-3.0.0-patches/ $srcdir/patches
}

function apply_patches {
    cd $srcdir
    if git checkout mininet ; then
	# Assume mininet 
        warn "Mininet branch already exists - not applying patches"
        return
    fi
    if [[ "$tag" != "" ]] ; then
	git checkout $tag
    fi
    git checkout -b mininet 
    warn "Applying patches..."
    git am -3 patches/*.patch
    work_around_kernel_package_bug
}

# lxc/ns and cfs configuration flags

config_y='
CONFIG_GROUP_SCHED
CONFIG_FAIR_GROUP_SCHED
CONFIG_RT_GROUP_SCHED
CONFIG_CGROUP_SCHED
CONFIG_CGROUPS
CONFIG_CGROUP_FREEZER
CONFIG_CGROUP_DEVICE
CONFIG_SCHED_AUTOGROUP
CONFIG_BLK_CGROUP
CONFIG_CFQ_GROUP_IOSCHED
CONFIG_CGROUP_PERF
CONFIG_CPUSETS
CONFIG_PROC_PID_CPUSET
CONFIG_CGROUP_CPUACCT
CONFIG_RESOURCE_COUNTERS
CONFIG_CGROUP_MEM_RES_CTLR
CONFIG_CGROUP_MEM_RES_CTLR_SWAP
CONFIG_MM_OWNER
CONFIG_NAMESPACES
CONFIG_UTS_NS
CONFIG_IPC_NS
CONFIG_USER_NS
CONFIG_PID_NS
CONFIG_NET_NS
CONFIG_NET_CLS_CGROUP
CONFIG_SECURITY_FILE_CAPABILITIES
CONFIG_DEVPTS_MULTIPLE_INSTANCES
CONFIG_VETH
CONFIG_VLAN_8021Q
CONFIG_MACVLAN
CONFIG_CFS_BANDWIDTH
CONFIG_NET_SCHED'

config_m='
CONFIG_BRIDGE
CONFIG_NET_SCH_CBQ
CONFIG_NET_SCH_HTB
CONFIG_NET_SCH_HFSC
CONFIG_NET_SCH_PRIO
CONFIG_NET_SCH_MULTIQ
CONFIG_NET_SCH_RED
CONFIG_NET_SCH_SFB
CONFIG_NET_SCH_SFQ
CONFIG_NET_SCH_TEQL
CONFIG_NET_SCH_TBF
CONFIG_NET_SCH_GRED
CONFIG_NET_SCH_DSMARK
CONFIG_NET_SCH_NETEM
CONFIG_NET_SCH_DRR
CONFIG_NET_SCH_MQPRIO
CONFIG_NET_SCH_CHOKE
CONFIG_NET_SCH_QFQ
CONFIG_NET_SCH_INGRESS
'

config_n='
CONFIG_SECURITY_APPARMOR
'

function configure_kernel {
    cd $srcdir
    warn "Configuring kernel..."

    if [[ "$menuconfig" == 'true' ]]; then
        make menuconfig
    else
        if [[ "$kconfig" == "" ]]; then
            warn "Using current kernel config..."
        else
            warn "Using specified kernel config: ${kconfig}..."
            cp $kconfig .config
        fi

        warn "Making oldconfig..."
        if [[ "$i386" == 'true' ]]; then
            linux32=linux32
        else
            linux32=
        fi
        yes '' | $linux32 make oldconfig 1> /dev/null
        if [[ "$localmodconfig" == 'true' ]]; then
            warn "Making localmodconfig..."
            yes '' | $linux32 make localmodconfig 1> /dev/null
        fi
        warn "Setting kernel flags for lxc and cbw..."
        for flag in $config_y; do
            if ! grep $flag .config 1> /dev/null; then
                echo $flag=y >> .config
            else
                sed -i -s "s/# $flag is not set/$flag=y/" .config
            fi
        done
        for flag in $config_m; do
            if ! grep $flag .config 1> /dev/null; then 
                echo $flag=m >> .config
            else
                sed -i -s "s/# $flag is not set/$flag=m/" .config
                sed -i -s "s/$flag=y/$flag=m/" .config
            fi
        done
        for flag in $config_n; do
            if ! grep $flag .config 1> /dev/null; then
                echo "# $flag is not set" >> .config
            else
                sed -i -s "s/$flag=y/# $flag is not set/" .config
                sed -i -s "s/$flag=m/# $flag is not set/" .config
            fi
        done
        for flag in $config_y $config_m; do 
            grep $flag .config || echo "WARNING: $flag IS MISSING"
        done
        cp .config /tmp
        warn "RAN CONFIG IN `pwd`"
    fi
}

function build_kernel {
    # Have your favourite build method here
    # This is a standard Debian way of building the kernel
    # The patches select cfs bandwidth automatically
    warn "Building kernel-$version_string"
    cd $srcdir
    procs=`grep -c ^processor /proc/cpuinfo`
    procs=`echo $procs + 2 | bc`
    export CONCURRENCY_LEVEL=$procs
    if [[ "$i386" == 'true' ]]; then
        mkpkg_extra_args='--cross-compile - --arch i386'
    else
        mkpkg_extra_args=
    fi
    make-kpkg clean $mkpkg_extra_args
    yes '' | fakeroot make-kpkg -j $procs $mkpkg_extra_args --initrd --append-to-version=${version_string} \
        kernel_image kernel_headers
}

function mod_kernel_dpkg {
    # Only needed for i386.
    cd /usr/src
    if [[ "$i386" == 'true' ]]; then
        warn "Modifying deb-pkg names for i386"
        # Based on instructions from http://dotcommie.net/?id=165
        for pkg_type in linux-image linux-headers; do
            pkg_name_orig=${pkg_type}-$kver${version_string}${plus}_$kver${version_string}${plus}-10.00.Custom_amd64.deb
            #hook=`readlink -f set_debian_control_i386.sh`
            hook=${orig_dir}/set_debian_control_i386.sh
            warn "$pkg_name_orig"
            fakeroot deb-reversion -s "" --hook $hook $pkg_name_orig
            # Remove the 1 in the name that deb-reversion adds.
            pkg_name_mod=${pkg_type}-$kver${version_string}${plus}_$kver${version_string}${plus}-10.00.Custom1_i386.deb
            pkg_name_new=${pkg_type}-$kver${version_string}${plus}_$kver${version_string}${plus}-10.00.Custom_i386.deb
            mv $pkg_name_mod $pkg_name_new
            warn "Removing original package: $pkg_name_orig"
            rm -f $pkg_name_orig
       done
    fi
}

function install_headers {
    warn "Installing headers..."
    sudo dpkg -i /usr/src/linux-headers-$kver${version_string}${plus}_$kver${version_string}${plus}-10.00.Custom_*.deb
}

function install_kernel {
    warn "Installing kernel..."
    sudo dpkg -i /usr/src/linux-image-$kver${version_string}${plus}_$kver${version_string}${plus}-10.00.Custom_*.deb
}

function build_initrd {
    # Certain versions of Ubuntu install a make-kpkg"
    # that does not build an initrd along with the rest of the kernel."
    warn "Building initrd..."
    #sudo mkdir -p /lib/modules/$kver${version_string}
    sudo mkinitramfs -v -k -o /boot/initrd.img-$kver${version_string}${plus} $kver${version_string}${plus}
}

function build_ovs_datapath {
    sudo apt-get install openvswitch-datapath-source
    if [[ "$i386" == 'true' ]]; then
        prepend='DEB_HOST_ARCH=i386 '
    else
        prepend=
    fi
    $prepend sudo module-assistant auto-build openvswitch-datapath -l $kver${version_string}${plus}
}

function mod_ovs_dpkg {
    # Only needed for i386.
    cd /usr/src
	if [[ "$i386" == 'true' ]]; then
        warn "Modifying deb-pkg names for i386"
	    # Based on instructions from http://dotcommie.net/?id=165
        for pkg_type in openvswitch-datapath-module; do
            pkg_name_orig=${pkg_type}-$kver${version_string}${plus}_${ovs_pkg_ver}_amd64.deb
            #hook=`readlink -f set_debian_control_i386.sh`
            hook=${orig_dir}/set_debian_control_i386.sh
            warn "$pkg_name_orig"
            fakeroot deb-reversion -s "" --hook $hook $pkg_name_orig
            # Remove the 1 in the name that deb-reversion adds.
            pkg_name_mod=${pkg_type}-$kver${version_string}${plus}_${ovs_pkg_ver}1_i386.deb
            pkg_name_new=${pkg_type}-$kver${version_string}${plus}_${ovs_pkg_ver}_i386.deb
            mv $pkg_name_mod $pkg_name_new
		    warn "Removing original package: $pkg_name_orig"
		    rm -f $pkg_name_orig
	   done
	fi
}

function install_ovs_datapath {
    warn "Installing ovs datapath"
    sudo module-assistant install openvswitch-datapath -l $kver${version_string}${plus}
}

parse_opts $*

if [[ "$install_only" != 'true' ]] ; then
    pre_check

    sudo chmod 777 $kdir
    cd $kdir

    fetch_kernel
    copy_patches
    apply_patches
    configure_kernel
    build_kernel
    mod_kernel_dpkg
    warn "******************************************"
    warn "Check for kernel .deb installation file in /usr/src/ along with initrd."
else
    install_headers
fi

if [[ "$i386" != 'true' ]]; then
    # Presumably we'll only want to install on a 64-bit machine.
    install_kernel
fi

build_ovs_datapath
mod_ovs_dpkg

if [[ "$i386" != 'true' ]]; then
    install_ovs_datapath
    build_initrd
fi

cd $orig_dir
warn "Done (hopefully)"
