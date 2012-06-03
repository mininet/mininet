#!/bin/bash
# Install lxc from source, apply patch, install
# (instructions tested with 2.6.35 only):
sudo apt-get -y install libcap-dev quilt
cd ~/
git clone git://lxc.git.sourceforge.net/gitroot/lxc/lxc
cd lxc
git checkout lxc-0.7.2 -b lxc-0.7.2
cp ~/mininet/util/kbuild/cfs-nsfd-kernel/lxc-patches.tar.gz .
tar xzf lxc-patches.tar.gz
# Modify patch.  Small change to the patch:  remove the 2nd argument to lxc_cgroup_path_get (it's set to NULL in the patch)
sed -i -s 's/cgrouppath, NULL, my_args.name/cgrouppath, my_args.name/' patches/lxc-attach-bug-fix.patch
quilt push -a
./autogen.sh
./configure
make
sudo make install
