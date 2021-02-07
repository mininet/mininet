#!/usr/bin/env python

"""
bind.py: Bind mount example

This creates hosts with private directories that the user specifies.
These hosts may have persistent directories that will be available
across multiple mininet session, or temporary directories that will
only last for one mininet session. To specify a persistent
directory, add a tuple to a list of private directories:

    [ ( 'directory to be mounted on', 'directory to be mounted' ) ]

String expansion may be used to create a directory template for
each host. To do this, add a %(name)s in place of the host name
when creating your list of directories:

    [ ( '/var/run', '/tmp/%(name)s/var/run' ) ]

If no persistent directory is specified, the directories will default
to temporary private directories. To do this, simply create a list of
directories to be made private. A tmpfs will then be mounted on them.

You may use both temporary and persistent directories at the same
time. In the following privateDirs string, each host will have a
persistent directory in the root filesystem at
"/tmp/(hostname)/var/run" mounted on "/var/run". Each host will also
have a temporary private directory mounted on "/var/log".

    [ ( '/var/run', '/tmp/%(name)s/var/run' ), '/var/log' ]

This example has both persistent directories mounted on '/var/log'
and '/var/run'. It also has a temporary private directory mounted
on '/var/mn'
"""

from functools import partial

from mininet.net import Mininet
from mininet.node import Host
from mininet.cli import CLI
from mininet.topo import SingleSwitchTopo
from mininet.log import setLogLevel, info


# Sample usage

def testHostWithPrivateDirs():
    "Test bind mounts"
    topo = SingleSwitchTopo( 10 )
    privateDirs = [ ( '/var/log', '/tmp/%(name)s/var/log' ),
                    ( '/var/run', '/tmp/%(name)s/var/run' ),
                      '/var/mn' ]
    host = partial( Host,
                    privateDirs=privateDirs )
    net = Mininet( topo=topo, host=host, waitConnected=True )
    net.start()
    directories = [ directory[ 0 ] if isinstance( directory, tuple )
                    else directory for directory in privateDirs ]
    info( 'Private Directories:', directories, '\n' )
    CLI( net )
    net.stop()


if __name__ == '__main__':
    setLogLevel( 'info' )
    testHostWithPrivateDirs()
    info( 'Done.\n')
