#!/usr/bin/env bash

# Mininet ssh authentication script for cluster edition

user=$(whoami)
declare -a hosts=()
SSHDIR=/tmp/mn/ssh
usage=$'./authenticate [ -p|h ] [ host1 ] [ host2 ] ...\n
        Authenticate yourself and other cluster nodes to each other
        via ssh for mininet cluster edition'

if [ -z "$1" ]; then
    echo "ERROR: No Arguments"
    echo "$usage"
    exit
fi

if [ "$1" == "-p" ]; then
    persistent=true
    shift
else
    persistent=false
fi

if [ "$1" == "-h" ]; then
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

echo "***authenticating to:"
for host in $hosts; do
    echo "$host"
done

echo ""

persistentSetup() {
    USERDIR=/home/$user/.ssh
    ROOTDIR=/root/.ssh
    echo "***creating key pair"
    ssh-keygen -t rsa -C "Cluster_Edition_Key" -f $USERDIR/cluster_key -N '' &> /dev/null
    sudo cp $USERDIR/{cluster_key,cluster_key.pub} $ROOTDIR
    sudo cat $USERDIR/cluster_key.pub >> $USERDIR/authorized_keys
    sudo sh -c "cat $ROOTDIR/cluster_key.pub >> $ROOTDIR/authorized_keys"
    echo "***configuring ssh"
    echo "IdentityFile $USERDIR/cluster_key" >> $USERDIR/config
    sudo sh -c "echo 'IdentityFile $ROOTDIR/cluster_key' >> $ROOTDIR/config"

    for host in $hosts; do
        echo "***copying public key to $host"
        sudo ssh-copy-id  -i $ROOTDIR/cluster_key.pub $user@$host &> /dev/null
        echo "***copying key pair to remote host"
        sudo scp $USERDIR/cluster_key $user@$host:$USERDIR
        sudo scp $USERDIR/cluster_key.pub $user@$host:$USERDIR
        echo "***configuring remote host"
        sudo ssh -o ForwardAgent=yes  $user@$host "
        sudo sh -c 'cp $USERDIR/cluster_key $ROOTDIR/cluster_key'
        sudo sh -c 'cp $USERDIR/cluster_key.pub $ROOTDIR/cluster_key.pub'
        sudo sh -c 'cat $USERDIR/cluster_key.pub >> $ROOTDIR/authorized_keys'
        echo 'IdentityFile $USERDIR/cluster_key' >> $USERDIR/config
        sudo sh -c 'echo "IdentityFile $ROOTDIR/cluster_key" >> $ROOTDIR/config'"
    done

    for host in $hosts; do
        echo "***copying known_hosts to $host"
        sudo cat $ROOTDIR/known_hosts >> $USERDIR/known_hosts
        sudo scp $ROOTDIR/known_hosts $user@$host:$USERDIR/cluster_known_hosts
        ssh $user@$host "
        cat $USERDIR/cluster_known_hosts >> $USERDIR/known_hosts
        sudo sh -c 'cat $USERDIR/cluster_known_hosts >> $ROOTDIR/known_hosts'
        rm $USERDIR/cluster_known_hosts"
    done
}

tempSetup() {
    
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
}

if $persistent; then
    echo "***Setting up persistent SSH configuration between all nodes"
    persistentSetup
    echo "\n*** Sucessfully set up ssh throughout the cluster!"
else
    echo "*** Setting up temporary SSH configuration between all nodes"
    tempSetup
    echo $'\n***Finished temporary setup. When you are done with your cluster'
    echo $'   session, tear down the SSH connections with'
    echo $'   ./clustercleanup.sh '$hosts''
fi

echo
