#!/bin/sh
#Brandon Heller (brandonh@stanford.edu)
#Install OVS deps on Debian Lenny

#The following files were useful for the install process:
#OVS INSTALL file:
#http://openvswitch.org/cgi-bin/gitweb.cgi?p=openvswitch;a=blob_plain;f=INSTALL.Linux;hb=HEAD

#OVS OpenFlow INSTALL file:
#http://openvswitch.org/cgi-bin/gitweb.cgi?p=openvswitch;a=blob_plain;f=INSTALL.OpenFlow;hb=HEAD

#OVS README file:
#http://openvswitch.org/cgi-bin/gitweb.cgi?p=openvswitch;a=blob_plain;f=README;hb=HEAD

#Install Autoconf 2.63+ backport from Debian Backports repo:
#Instructions from http://backports.org/dokuwiki/doku.php?id=instructions
sudo apt-get -y install debian-backports-keyring
sudo su -c "echo 'deb http://www.backports.org/debian lenny-backports main contrib non-free' >> /etc/apt/sources.list"
sudo apt-get update
sudo apt-get -y -t lenny-backports install autoconf