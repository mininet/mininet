# -*- mode: ruby -*-
# vi: set ft=ruby :

BOX_NAME = ENV["BOX_NAME"] || "precise64"
BOX_URL  = ENV["BOX_URL"]  || "http://cloud-images.ubuntu.com/vagrant/precise/current/precise-server-cloudimg-amd64-vagrant-disk1.box"
VAGRANTFILE_API_VERSION = "2"

Vagrant.configure(VAGRANTFILE_API_VERSION) do |config|
  config.vm.box = BOX_NAME
  config.vm.box_url = BOX_URL
  cmd = [
    "mkdir mininet",
    "cp -rv /vagrant/* mininet/",
    "cd mininet && ./util/install.sh -nfv"
  ]
  config.vm.provision :shell, inline: cmd.join(" && ")
end
