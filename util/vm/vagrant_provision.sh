#!/usr/bin/env bash
# This script is intended to install Mininet into
# a brand-new Ubuntu virtual machine,
# to create a fully usable "tutorial" VM.
#
# optional argument: Mininet branch to install

set -euo pipefail

# sudo apt-get -qq update && sudo apt-get -qq -y upgrade > /dev/null

sudo sed -i -e 's/Default/#Default/' /etc/sudoers
sudo sed -i -e 's/quiet/text/' /etc/default/grub
sudo update-grub

# Clean up vmware easy install junk if present
if [ -e /etc/issue.backup ]; then
    sudo mv /etc/issue.backup /etc/issue
fi
if [ -e /etc/rc.local.backup ]; then
    sudo mv /etc/rc.local.backup /etc/rc.local
fi

# Fetch Mininet
git clone https://github.com/mininet/mininet --branch "${1:-master}"

# Install Mininet for Python3
sudo apt-get -qq -y install python-is-python3
time PYTHON=python3 mininet/util/install.sh

# Finalize VM
time mininet/util/install.sh -tc
sudo mn --test pingall
echo "Done preparing Mininet VM."
