#!/bin/bash

# This script is intended to install Mininet into
# a brand-new Ubuntu virtual machine,
# to create a fully usable "tutorial" VM.
set -e
echo `whoami` ALL=NOPASSWD: ALL | sudo tee -a /etc/sudoers
sudo sed -i -e 's/Default/#Default/' /etc/sudoers
sudo sed -i -e 's/ubuntu/mininet-vm/' /etc/hostname
sudo sed -i -e 's/ubuntu/mininet-vm/g' /etc/hosts
sudo hostname `cat /etc/hostname`
sudo sed -i -e 's/quiet splash/text/' /etc/default/grub
sudo update-grub
sudo sed -i -e 's/us.archive.ubuntu.com/mirrors.kernel.org/' \
	/etc/apt/sources.list
sudo apt-get update
# Clean up vmware easy install junk if present
if [ -e /etc/issue.backup ]; then
    sudo mv /etc/issue.backup /etc/issue
fi
if [ -e /etc/rc.local.backup ]; then
    sudo mv /etc/rc.local.backup /etc/rc.local
fi
# Install Mininet
sudo apt-get -y install git-core openssh-server
git clone git://github.com/mininet/mininet
cd mininet
cd
time mininet/util/install.sh
# Ignoring this since NOX classic is deprecated
#if ! grep NOX_CORE_DIR .bashrc; then
#  echo "export NOX_CORE_DIR=~/noxcore/build/src/" >> .bashrc
#fi
echo <<EOF
You may need to reboot and then:
sudo dpkg-reconfigure openvswitch-datapath-dkms
sudo service openvswitch-switch start
EOF


