# -*- mode: ruby -*-
# vi: set ft=ruby :

# Install docker on ubuntu trusty
# https://docs.docker.com/engine/installation/ubuntulinux/

$script = <<SCRIPT
apt-key adv --keyserver hkp://p80.pool.sks-keyservers.net:80 --recv-keys 58118E89F3A912897C070ADBF76221572C52609D
echo 'deb https://apt.dockerproject.org/repo ubuntu-trusty main' > /etc/apt/sources.list.d/docker.list
apt-get update
apt-cache policy docker-engine
apt-get install -y -q linux-image-extra-$(uname -r) \
                      docker-engine \
                      python-pip
service docker restart
pip install --upgrade pip
cd /vagrant
pip install -r requirements.txt
SCRIPT


Vagrant.configure("2") do |config|
  config.vm.box = "ubuntu/trusty64"
  config.ssh.forward_agent = true

  config.vm.define "dockerhost" do |master|
    master.vm.hostname = "dockerhost.vagrant.intern"
    master.vm.network :private_network, ip: "192.168.2.1"
  end

  config.vm.provision "shell", inline: $script
end