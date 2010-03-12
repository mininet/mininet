#!/bin/sh
#Brandon Heller (brandonh@stanford.edu)
#Install NOX deps on Debian Lenny

#Install NOX deps:
sudo apt-get -y install autoconf automake g++ libtool python python-twisted swig libboost1.35-dev libxerces-c2-dev libssl-dev make

#Install NOX optional deps:
sudo apt-get install -y libsqlite3-dev python-simplejson