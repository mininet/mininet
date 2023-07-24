# -*- mode: ruby -*-
# vi: set ft=ruby :
#
# The vagrant configuration for basic Mininet VMs.
# By default the configuraion will take any provider you have installed.
#
# The base image is an ubuntu 20.04, customised to have Mininet preinstalled.

Vagrant.configure("2") do |config|
  config.vm.hostname = "mininet-vm"

  config.vm.box = "generic/ubuntu2004"
  config.vm.box_version = "3.6.8"

  config.vm.provider :libvirt do |lv|
    lv.title = "mininet"
    lv.memory = "2048"
  end

  config.vm.provision "shell", path: "./util/vm/vagrant_provision.sh", args: ENV['BRANCH']
end
