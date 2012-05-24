#!/bin/bash

# This script is intended to install Mininet into
# a brand-new Ubuntu (10.04 or 11.10) virtual machine,
# to create a fully usable "tutorial" VM.

set -e
sudo sh -c 'cat >> /etc/sudoers' <<EOF
openflow ALL=NOPASSWD: ALL
EOF
sudo sed -i -e 's/Default/#Default/' /etc/sudoers
sudo sed -i -e 's/ubuntu/mininet-vm/' /etc/hostname
sudo sed -i -e 's/ubuntu/mininet-vm/g' /etc/hosts
sudo hostname `cat /etc/hostname`
sudo sed -i -e 's/quiet splash/text/' /etc/default/grub
sudo update-grub
sudo sed -i -e 's/us.archive.ubuntu.com/mirrors.kernel.org/' \
	/etc/apt/sources.list
sudo apt-get update
sudo apt-get -y install git-core openssh-server
git clone git://github.com/mininet/mininet
cd mininet
cd
time mininet/util/install.sh
if ! grep NOX_CORE_DIR .bashrc; then
  echo "export NOX_CORE_DIR=~/noxcore/build/src/" >> .bashrc
fi
echo <<EOF
You may need to reboot and then:
sudo dpkg-reconfigure openvswitch-datapath-dkms
sudo service openvswitch-switch start
EOF


