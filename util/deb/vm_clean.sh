#!/bin/sh
#Brandon Heller (brandonh@stanford.edu)
#Clean up after VM installation

sudo apt-get clean
sudo rm -rf /tmp/*
history -c
rm ~/.ssh/id_rsa*
sudo rm ~/.ssh/authorized_keys2
sudo rm -rf ~/mininet