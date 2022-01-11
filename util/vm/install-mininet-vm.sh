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
sudo apt-get -qq update
# Clean up vmware easy install junk if present
if [ -e /etc/issue.backup ]; then
    sudo mv /etc/issue.backup /etc/issue
fi
if [ -e /etc/rc.local.backup ]; then
    sudo mv /etc/rc.local.backup /etc/rc.local
fi
# Fetch Mininet
sudo apt-get -y -qq install git-core openssh-server
git clone https://github.com/mininet/mininet
# Optionally check out branch
if [ "$1" != "" ]; then
    pushd mininet
    git fetch origin $1
    git checkout $1
    popd
fi
# Install Mininet for Python2 and Python3
APT="sudo apt-get -y -qq"
$APT install python3
$APT install python2 || $APT install python
python --version || $APT install python-is-python3
time PYTHON=python2 mininet/util/install.sh -n
time PYTHON=python3 mininet/util/install.sh
# Finalize VM
time mininet/util/install.sh -tcd
# Ignoring this since NOX classic is deprecated
#if ! grep NOX_CORE_DIR .bashrc; then
#  echo "export NOX_CORE_DIR=~/noxcore/build/src/" >> .bashrc
#fi
echo "Done preparing Mininet VM."
