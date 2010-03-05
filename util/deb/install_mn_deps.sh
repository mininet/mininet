#!/bin/sh
#Brandon Heller (brandonh@stanford.edu)
#Install Mininet deps on Debian Lenny

#Install dependencies:
sudo apt-get install -y screen psmisc xterm ssh iperf iproute python-setuptools

#Get the source, with the customtopos branch (for now, this should be removed shortly):
git clone git@yuba.stanford.edu:mininet.git
cd ~/mininet
git checkout -b customtopos origin/customtopos

#Add sysctl parameters as noted in the INSTALL file to increase kernel limits to support larger setups:
sudo su -c "cat /home/mininet/mininet/sysctl_addon >> /etc/sysctl.conf"

#Load sysctl settings:
sudo sysctl -p

#Reboot to ensure you start with higher limits and verify that the IPv6 module is not loaded, plus there's an unknown issue where you need to reboot before the kernel datapath will get added (sorry).
sudo reboot