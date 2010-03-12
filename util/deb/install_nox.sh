#!/bin/sh
#Brandon Heller (brandonh@stanford.edu)
#Install NOX on Debian Lenny

#Install NOX:
git clone git://noxrepo.org/noxcore
cd noxcore
./boot.sh
mkdir build
cd build
../configure --with-python=yes
make
#make check

#Add NOX_CORE_DIR env var;; modify ~/.bashrc:
sed -i -e 's|# for examples$|&\ncomplete -cf sudo|' ~/.bashrc