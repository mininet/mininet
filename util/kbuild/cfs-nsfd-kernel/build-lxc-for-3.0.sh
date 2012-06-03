#!/bin/bash
# Builds lxc for kernel patched with setns

# Check for unitialized variables
set -o nounset

# Exit on any failure
set -e

# Kernel version to use
kver=3.0

# Location in which to download and build lxc
lxcdir=$HOME
kdir=/lib/modules/`uname -r`/build

# lxc version to use
lxcver=lxc-0.7.5

# Save original directory for later.
orig_dir=`pwd`

function warn {
    # Echo the provided command in color text.
    yellow='\e[0;33m' # Yellow
    reset='\e[0m'
    echo="echo -e"
    $echo "${yellow}$1${reset}"
}

function usage {
    warn "Usage: $0 [lxc download location] [kernel location]"
}


if [[ "$#" > 2 ]]; then
    warn "Invalid number of args passed."
    usage
    exit
elif [[ "$#" == 0 ]]; then
    warn "No args passed."
    warn "Using default lxc location: ${lxcdir}." 
    warn "Using default kernel location: ${kdir}."
elif [[ "$#" == 1 ]]; then
    lxcdir=$1
    warn "Using custom lxc location: ${lxcdir}"
    warn "Using default kernel location: ${kdir}"
elif [[ "$#" == 2 ]]; then
    lxcdir=$1
    kdir=$2
    warn "Using custom lxc location: ${lxcdir}"
    warn "Using custom kernel location: ${kdir}"
fi

function pre_check {
    warn "Checking for git"
    if [[ -z `which git` ]]; then
        read -p \
            warn "You need git to download lxc.  Install? [Y/n] " \
            answer;
        [[ -z $answer || $answer=="Y" || $answer == "y" ]] && \
            sudo apt-get install git;
    fi

    warn "Checking for linux source code"
    if [[ ! -d ${kdir} ]]; then
        warn "Error: Kernel doesn't exist in ${kdir}... exiting"
        exit
    fi
}

function fetch_lxc {
    cd $lxcdir
    warn "--> Fetching lxc"
    if [[ -d lxc ]]; then
        warn "lxc source exists, skipping.."
        return
    fi
    git clone git://lxc.git.sourceforge.net/gitroot/lxc/lxc
    cd lxc
    git checkout $lxcver
    cd ..
}

function copy_patches {
    rm -rf lxc/patches
    cp -r ${orig_dir}/../../lxc-$kver-patches lxc/patches
}

function apply_patches {
    cd lxc
    warn "Applying patches..."
    git am -3 patches/*.patch
}

function build_lxc {
    warn "Building lxc with kernel-${kver}..."
    processors=`grep -c ^processor /proc/cpuinfo`
    export CONCURRENCY_LEVEL=$processors
    make distclean || true
    ./autogen.sh
    ./configure --with-linuxdir=${kdir}
    make
}

function install_lxc {
    warn "Installing lxc..."
    sudo make install
    # Seems to be missing
    sudo mkdir -p /usr/local/var/lib/lxc
}

usage
pre_check
fetch_lxc
copy_patches
apply_patches
build_lxc
install_lxc
cd $orig_dir
warn "Done (hopefully)"
