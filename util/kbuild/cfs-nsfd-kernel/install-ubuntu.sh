#!/bin/bash

# Check for unitialized variables
set -o nounset

# Exit on any failure
set -e

debdir=/usr/src
kver=3.0.9-with-cfs
kbuild=/lib/modules/$kver/build

if arch | grep 64 > /dev/null ; then arch=amd64; else arch=i386; fi

headers=linux-headers-${kver}_${kver}-10.00.Custom_${arch}.deb
image=linux-image-${kver}_${kver}-10.00.Custom_${arch}.deb
ovs=openvswitch-datapath-module-${kver}_1.2.0-1ubuntu3_${arch}.deb

echo "Mininet-hifi installer"

echo "1. Checking for prereqs"
  if [[ ! -e $debdir/$headers || ! -e $debdir/$image || 
	! -e $debdir/$ovs ]]; then
    echo "Can't find kernel packages"
    echo "$debdir/$headers or $debdir/$image or $debdir/$ovs is missing"
    exit 1
  fi
  if [[ "`ssh-add -l`" == "" ]]; then
    echo "No SSH keys - nsdi repo checkout will fail."
    exit 1
  fi

echo "2. Getting mainline Mininet from github"
  cd ~
  git clone git://github.com/mininet/mininet.git

echo "3. Installing OpenFlow reference implementation"
  mininet/util/install.sh -f

echo "4. Installing Mininet core files"
  mininet/util/install.sh -n

echo "5. Adding nsdi repository"
  cd ~/mininet
  git remote add nsdi git@gitosis.stanford.edu:mininet-nsdi.git
  git fetch nsdi
  git checkout -b mininet-rt remotes/nsdi/mininet-rt
  sudo make install

echo "6. Installing kernel packages"
  sudo dpkg -i $debdir/$headers
  sudo dpkg -i $debdir/$image 
  sudo dpkg -i $debdir/$ovs
  
echo "7. Fetching, building and installing Open vSwitch user code"
  cd ~
  git clone git://openvswitch.org/openvswitch
  cd ~/openvswitch
  git checkout v1.2.2
  ./boot.sh
  ./configure
  make all
  sudo make install
  sudo cp tests/test-openflowd /usr/local/bin/ovs-openflowd

echo "8. Building and installing custom lxc package"
  sudo apt-get -y install libcap-dev
  cd ~/mininet/util/kbuild/cfs-nsfd-kernel
  ./build-lxc-for-3.0.sh $HOME $kbuild 

echo "9. Setting up /cgroup"
  sudo apt-get remove cgroup-lite
  sudo mkdir /cgroup
  sudo sh -c "echo 'cgroup /cgroup cgroup defaults 0 0' >> /etc/fstab"

echo "10. Creating /etc/mn/host.conf"
  sudo mkdir -p /etc/mn
  sudo sh -c "echo 'lxc.utsname = mnhost' > /etc/mn/host.conf"
  sudo sh -c "echo 'lxc.network.type = empty' >> /etc/mn/host.conf"

echo "11. Getting rid of quiet boot"
  sudo sed -i 's/quiet/text/' /etc/default/grub

echo "Done! reboot to test"

