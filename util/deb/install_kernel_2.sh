#!/bin/sh
#Brandon Heller (brandonh@stanford.edu)
#Clean up custom kernel on Debian Lenny (part 2)

#To save disk space, remove previous kernel
sudo apt-get -y remove linux-image-2.6.26-2-686

#Also remove downloaded packages:
rm linux-headers-2.6.29.6-custom_2.6.29.6-custom-10.00.Custom_i386.deb linux-image-2.6.29.6-custom_2.6.29.6-custom-10.00.Custom_i386.deb