#!/usr/bin/env bash

# Mininet ssh authentication script for cluster edition
# to-do:
# check for passwordless sudo on remote machines and own machine
# check for user on remote machines?
# make a persistent option

user=$(whoami)
declare -a hosts=()
SSHDIR=/tmp/mn/ssh
usage=$'./authenticate [ host1 ] [ host2 ] ...\n
        Authenticate yourself and other cluster nodes to each other
        via ssh for mininet cluster edition'

if [ -z "$1" ]; then
    echo "ERROR: Must input a hostname"
    echo "$usage"
    exit
fi

for i in "$@"; do
    output=$(getent ahostsv4 "$i")
    if [ -z "$output" ]; then
        echo '***WARNING: could not find hostname "$i"'
        echo ""
    else
        hosts+="$i "
    fi
done

echo $hosts

echo "***authenticating to:"
for host in $hosts; do
    echo "$host"
done

echo ""

echo "***creating temporary ssh directory"
mkdir -p $SSHDIR 
echo "***creating key pair"
ssh-keygen -t rsa -C "Cluster_Edition_Key" -f /tmp/mn/ssh/id_rsa -N '' &> /dev/null
echo "***mounting temporary ssh directory"
sudo mount --bind $SSHDIR /root/.ssh
sudo mount --bind $SSHDIR /home/$user/.ssh
cp $SSHDIR/id_rsa.pub $SSHDIR/authorized_keys

for host in $hosts; do
    echo "***copying public key to $host"
    sudo ssh-copy-id  -i /root/.ssh/id_rsa.pub $user@$host &> /dev/null
    echo "***mounting remote temporary ssh directory for $host"
    sudo ssh -o ForwardAgent=yes  $user@$host "mkdir -p /tmp/mn/ssh
    cp /home/$user/.ssh/authorized_keys $SSHDIR/authorized_keys
    sudo mount --bind $SSHDIR /root/.ssh
    sudo mount --bind $SSHDIR /home/$user/.ssh"
    echo "***copying key pair to $host"
    sudo scp $SSHDIR/{id_rsa,id_rsa.pub} $user@$host:$SSHDIR
done
for host in $hosts; do
    echo "***copying known_hosts to $host"
    sudo scp $SSHDIR/known_hosts $user@$host:$SSHDIR
done
echo "done!"
