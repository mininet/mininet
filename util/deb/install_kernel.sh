#!/bin/sh
#Brandon Heller (brandonh@stanford.edu)
#Install custom kernel on Debian Lenny

#The easy approach: download pre-built linux-image and linux-headers packages:
wget http://www.stanford.edu/~brandonh/linux-headers-2.6.29.6-custom_2.6.29.6-custom-10.00.Custom_i386.deb
wget http://www.stanford.edu/~brandonh/linux-image-2.6.29.6-custom_2.6.29.6-custom-10.00.Custom_i386.deb

#Install custom linux headers and image:
sudo dpkg -i linux-image-2.6.29.6-custom_2.6.29.6-custom-10.00.Custom_i386.deb linux-headers-2.6.29.6-custom_2.6.29.6-custom-10.00.Custom_i386.deb

#The default should be the new kernel. Otherwise, you may need to modify /boot/grub/menu.lst to set the default to the entry corresponding to the kernel you just installed.

#Reduce boot screen opt-out delay. Modify timeout in /boot/grub/menu.lst to 1:
sudo sed -i -e 's/^timeout.*$/timeout         1/' /boot/grub/menu.lst"