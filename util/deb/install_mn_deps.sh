#!/bin/sh
#Brandon Heller (brandonh@stanford.edu)
#Install Mininet deps on Debian Lenny

#Install dependencies:
sudo apt-get install -y screen psmisc xterm ssh iperf iproute python-setuptools

#Add sysctl parameters as noted in the INSTALL file to increase kernel limits to support larger setups:
sudo su -c "cat /home/mininet/mininet/util/sysctl_addon >> /etc/sysctl.conf"

#Load sysctl settings:
sudo sysctl -p