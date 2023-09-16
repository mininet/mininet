#!/usr/bin/env bash

# Mininet ssh authentication script for cluster edition
# This script will create a single key pair, which is then
# propagated throughout the entire cluster.
# There are two options for setup; temporary setup
# persistent setup. If no options are specified, and the script
# is only given ip addresses or host names, it will default to
# the temporary setup. An ssh directory is then created in
# /tmp/mn/ssh on each node, and mounted with the keys over the
# user's ssh directory. This setup can easily be torn down by running
# clustersetup with the -c option.
# If the -p option is used, the setup will be persistent. In this
# case, the key pair will be be distributed directly to each node's
# ssh directory, but will be called cluster_key. An option to
# specify this key for use will be added to the config file in each
# user's ssh directory.


set -e
num_options=0
persistent=false
showHelp=false
clean=false
declare -a hosts=()
user=$(whoami)
SSHDIR=/tmp/mn/ssh
USERDIR=$HOME/.ssh
usage="./clustersetup.sh [ -p|h|c ] [ host1 ] [ host2 ] ...\n
        Authenticate yourself and other cluster nodes to each other
        via ssh for mininet cluster edition. By default, we use a
        temporary ssh setup. An ssh directory is mounted over
        $USERDIR on each machine in the cluster.
        
                -h: display this help
                -p: create a persistent ssh setup. This will add
                    new ssh keys and known_hosts to each nodes
                    $USERDIR directory
                -c: method to clean up a temporary ssh setup.
                    Any hosts taken as arguments will be cleaned
        "

persistentSetup() {
    echo "***creating key pair"
    ssh-keygen -t rsa -C "Cluster_Edition_Key" -f $USERDIR/cluster_key -N '' &> /dev/null
    cat $USERDIR/cluster_key.pub >> $USERDIR/authorized_keys
    echo "***configuring ssh"
    echo "IdentityFile $USERDIR/cluster_key" >> $USERDIR/config
    echo "IdentityFile $USERDIR/id_rsa" >> $USERDIR/config

    for host in $hosts; do
        echo "***copying public key to $host"
        ssh-copy-id  -i $USERDIR/cluster_key.pub $user@$host &> /dev/null
        echo "***copying key pair to remote host"
        scp $USERDIR/cluster_key $user@$host:$USERDIR
        scp $USERDIR/cluster_key.pub $user@$host:$USERDIR
        echo "***configuring remote host"
        ssh -o ForwardAgent=yes  $user@$host "
        echo 'IdentityFile $USERDIR/cluster_key' >> $USERDIR/config
        echo 'IdentityFile $USERDIR/id_rsa' >> $USERDIR/config"
    done

    for host in $hosts; do
        echo "***copying known_hosts to $host"
        scp $USERDIR/known_hosts $user@$host:$USERDIR/cluster_known_hosts
        ssh $user@$host "
        cat $USERDIR/cluster_known_hosts >> $USERDIR/known_hosts
        rm $USERDIR/cluster_known_hosts"
    done
}

tempSetup() {
    
    echo "***creating temporary ssh directory"
    mkdir -p $SSHDIR 
    echo "***creating key pair"
    ssh-keygen -t rsa -C "Cluster_Edition_Key" -f $SSHDIR/id_rsa -N '' &> /dev/null

    echo "***mounting temporary ssh directory"
    sudo mount --bind $SSHDIR $USERDIR
    cp $SSHDIR/id_rsa.pub $SSHDIR/authorized_keys

    for host in $hosts; do
        echo "***copying public key to $host"
        ssh-copy-id $user@$host &> /dev/null
        echo "***mounting remote temporary ssh directory for $host"
        ssh -o ForwardAgent=yes  $user@$host "
        mkdir -p $SSHDIR
        cp $USERDIR/authorized_keys $SSHDIR/authorized_keys
        sudo mount --bind $SSHDIR $USERDIR"
        echo "***copying key pair to $host"
        scp $SSHDIR/{id_rsa,id_rsa.pub} $user@$host:$SSHDIR
    done

    for host in $hosts; do
        echo "***copying known_hosts to $host"
        scp $SSHDIR/known_hosts $user@$host:$SSHDIR
    done
}

cleanup() {
    
    for host in $hosts; do
    echo "***cleaning up $host"
    ssh $user@$host "sudo umount $USERDIR
                          sudo rm -rf $SSHDIR"
    done

    echo "**unmounting local directories"
    sudo umount $USERDIR
    echo "***removing temporary ssh directory"
    sudo rm -rf $SSHDIR
    echo "done!"

}


if [ $# -eq 0 ]; then
    echo "ERROR: No Arguments"
    echo "$usage"
    exit
else
    while getopts 'hpc' OPTION
    do
        ((num_options+=1))
        case $OPTION in
        h)  showHelp=true;;
        p)  persistent=true;;
        c)  clean=true;;
        ?)  showHelp=true;;
        esac
    done
    shift $(($OPTIND - 1))
fi

if [ "$num_options" -gt 1 ]; then
    echo "ERROR: Too Many Options"
    echo "$usage"
    exit
fi

if $showHelp; then
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

if $clean; then
    cleanup
    exit
fi

echo "***authenticating to:"
for host in $hosts; do
    echo "$host"
done

echo

if $persistent; then
    echo '***Setting up persistent SSH configuration between all nodes'
    persistentSetup
    echo $'\n*** Successfully set up ssh throughout the cluster!'

else
    echo '*** Setting up temporary SSH configuration between all nodes'
    tempSetup
    echo $'\n***Finished temporary setup. When you are done with your cluster'
    echo $'   session, tear down the SSH connections with'
    echo $'   ./clustersetup.sh -c '$hosts''
fi

echo
