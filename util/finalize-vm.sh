#!/usr/bin/env bash


# cleanup apt

sudo apt-get clean
sudo apt-get autoclean
sudo apt-get autoremove

# zero out all free disk space

cat /dev/zero  > zeros ; sync ; sleep 1 ; sync ; rm -f zeros

sudo halt

