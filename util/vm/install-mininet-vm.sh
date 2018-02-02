#!/bin/bash

# This script is intended to install Mininet into
# a brand-new Ubuntu virtual machine,
# to create a fully usable "tutorial" VM.
#
# optional argument: Mininet branch to install
set -e
echo "$(whoami) ALL=(ALL) NOPASSWD:ALL" | sudo tee -a /etc/sudoers > /dev/null
sudo sed -i -e 's/Default/#Default/' /etc/sudoers
echo mininet-vm | sudo tee /etc/hostname > /dev/null
sudo sed -i -e 's/ubuntu/mininet-vm/g' /etc/hosts
sudo hostname `cat /etc/hostname`
sudo sed -i -e 's/splash//' /etc/default/grub
sudo sed -i -e 's/quiet/text/' /etc/default/grub
sudo update-grub
# Update from official archive
sudo apt-get update
# 12.10 and earlier
#sudo sed -i -e 's/us.archive.ubuntu.com/mirrors.kernel.org/' \
#	/etc/apt/sources.list
# 13.04 and later
#sudo sed -i -e 's/\/archive.ubuntu.com/\/mirrors.kernel.org/' \
#	/etc/apt/sources.list
# Clean up vmware easy install junk if present
if [ -e /etc/issue.backup ]; then
    sudo mv /etc/issue.backup /etc/issue
fi
if [ -e /etc/rc.local.backup ]; then
    sudo mv /etc/rc.local.backup /etc/rc.local
fi
# Fetch Mininet
sudo apt-get -y install git-core openssh-server
git clone git://github.com/mininet/mininet
# Optionally check out branch
if [ "$1" != "" ]; then
  pushd mininet
  #git checkout -b $1 $1
  # TODO branch will in detached HEAD state if it is not master
  git checkout $1
  popd
fi
# Install Mininet
time mininet/util/install.sh
# Finalize VM
time mininet/util/install.sh -tcd
# Ignoring this since NOX classic is deprecated
#if ! grep NOX_CORE_DIR .bashrc; then
#  echo "export NOX_CORE_DIR=~/noxcore/build/src/" >> .bashrc
#fi
echo "Done preparing Mininet VM."
