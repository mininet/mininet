#!/bin/sh
#Brandon Heller (brandonh@stanford.edu)
#Install NOX on Debian Lenny

#Install NOX deps:
sudo apt-get -y install autoconf automake g++ libtool python python-twisted swig libboost1.35-dev libxerces-c2-dev libssl-dev make

#Install NOX optional deps:
sudo apt-get install -y libsqlite3-dev python-simplejson

#Install NOX:
git clone git://noxrepo.org/noxcore
cd noxcore
./boot.sh
mkdir build
cd build
../configure --with-python=yes
make
#make check