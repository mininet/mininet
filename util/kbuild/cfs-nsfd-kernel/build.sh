#!/bin/bash
# Builds kernel with the new CFS Bandwidth patches
# and nsfd/setns syscall patches.

# Check for unitialized variables
set -o nounset

# Exit on any failure
set -e

# Location in which to download and build the kernel
kdir=/usr/src

# Kernel version to download
kver=2.6.35

# Save original directory for later.
orig_dir=`pwd`

# Kernel version string
version_string=-with-cfs

# Run menuconfig later?
menuconfig=

function warn {
    # Echo the provided command in color text.
    yellow='\e[0;33m' # Yellow
    reset='\e[0m'
    echo="echo -e"
    $echo "${yellow}$1${reset}"
}

function usage {
    warn "Usage: build.sh [version string] [menuconfig]"
}


if [[ "$#" > 2 ]]; then
    warn "Invalid number of args passed."
    usage
    exit
elif [[ "$#" == 0 ]]; then
    warn "No args passed.  Using default version_string: ${version_string}"
elif [[ "$#" == 1 ]]; then
    warn "Using custom version_string: ${version_string}"
    version_string=$1
elif [[ "$#" == 2 && $2 != 'menuconfig' ]]; then
    warn "Second arg is either menuconfig or missing."
    usage
else
    version_string=$1
    menuconfig=true
fi

function pre_check {
    warn "Checking for kernel-package build utilities"
    if [[ -z `which make-kpkg` ]]; then
        read -p \
            warn "You need kernel-package utilities to build the kernel.  Install? [Y/n] " \
            answer;
        [[ -z $answer || $answer=="Y" || $answer == "y" ]] && \
            sudo apt-get install kernel-package ncurses-dev;
    fi
    
    warn "Checking for quilt"
    if [[ -z `which quilt` ]]; then
        read -p \
            warn "You need quilt to install patches.  Install? [Y/n] " \
            answer;
        [[ -z $answer || $answer=="Y" || $answer == "y" ]] && \
            sudo apt-get install quilt;
    fi
}

function fetch_kernel {
    warn "--> Fetching kernel linux-$kver"
    if [[ -f linux-$kver.tar.bz2 ]]; then
        warn "File exists, skipping.."
        return
    fi
    wget http://kernel.org/pub/linux/kernel/v2.6/linux-$kver.tar.bz2
    warn "Unpacking kernel"
    tar xjf linux-$kver.tar.bz2
}

function work_around_kernel_package_bug {
    # Fix will likely break on any other kernel version, so watch out.
    # From:
    # https://bugs.launchpad.net/ubuntu/+source/kernel-package/+bug/58307/comments/16
    sed -i -s 's/echo "+"/#echo "+"/' linux-${kver}/scripts/setlocalversion
}

function copy_patches {
    rm -rf linux-$kver/patches
    cp -r ${orig_dir}/../../linux-2.6.35-patches linux-$kver/patches
}

function apply_patches {
    cd linux-$kver
    # Apply patch series only if not applied previously.
    # A better check would look at patches/series and make sure each entry
    # in `quilt applied` was covered.
    warn "Checking for applied patches"
    quilt applied > quilt_applied_stdout 2> quilt_applied_stderr || true
    if [[ `grep -c "No patches applied" quilt_applied_stderr` == 1 ]]; then
        warn "Applying patches"
        quilt push -a
    else
        warn "Skipped patches"
    fi
    rm quilt_applied
}

function build_kernel {
    # Have your favourite build method here
    # This is a standard Debian way of building the kernel
    # The patches select cfs bandwidth automatically
    warn "Building kernel..."

    if [[ "$menuconfig" == 'true' ]]; then
        make menuconfig
    else
        warn "Making oldconfig..."
        yes "" | make oldconfig
        warn "Making localmodconfig..."
        make localmodconfig
        warn "Enabling netns and cpubw..."
        sed -i -s 's/# CONFIG_VETH is not set/CONFIG_VETH=y/' .config
        sed -i -s 's/CONFIG_BRIDGE=y/CONFIG_BRIDGE=m/' .config
        sed -i -s 's/# CONFIG_BRIDGE is not set/CONFIG_BRIDGE=m/' .config
        sed -i -s 's/# CONFIG_CFS_BANDWIDTH is not set/CONFIG_CFS_BANDWIDTH=y/' .config
        sed -i -s 's/# CONFIG_NET_NS is not set/CONFIG_NET_NS=y/' .config
    fi

    warn "Building kernel-$version_string"
    processors=`grep -c ^processor /proc/cpuinfo`
    export CONCURRENCY_LEVEL=$processors
    yes "" | fakeroot make-kpkg --initrd --append-to-version=${version_string} kernel_image
  
    warn "******************************************"
    warn "Check for kernel .deb installation file in ../ along with initrd."
}

function install_kernel {
    warn "Installing kernel..."
    sudo dpkg -i /usr/src/linux-image-$kver${version_string}_$kver${version_string}-10.00.Custom_amd64.deb
}

function build_initrd {
    # Certain versions of Ubuntu install a make-kpkg"
    # that does not build an initrd along with the rest of the kernel."
    warn "Building initrd..."
    #sudo mkdir -p /lib/modules/$kver${version_string}
    sudo mkinitramfs -v -k -o /boot/initrd.img-$kver${version_string} $kver${version_string}
}

pre_check

sudo chmod 777 $kdir
cd $kdir

fetch_kernel
work_around_kernel_package_bug
copy_patches
apply_patches
build_kernel
install_kernel
build_initrd
warn "Done (hopefully)"
