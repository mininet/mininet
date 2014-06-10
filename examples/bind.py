#!/usr/bin/python

"""
bind.py: Bind mount prototype

This creates hosts with private directories as desired.
"""

from mininet.net import Mininet
from mininet.node import Host, HostWithPrivateDirs
from mininet.cli import CLI
from mininet.topo import SingleSwitchTopo
from mininet.log import setLogLevel, info, debug

from functools import partial


# Sample usage

def testHostWithPrivateDirs():
    "Test bind mounts"
    topo = SingleSwitchTopo( 10 )
    privateDirs = [ '/var/log', '/var/run' ]
    host = partial( HostWithPrivateDirs,
                    privateDirs=privateDirs )
    net = Mininet( topo=topo, host=host )
    net.start()
    info( 'Private Directories:', privateDirs, '\n' )
    CLI( net )
    net.stop()


if __name__ == '__main__':
    setLogLevel( 'info' )
    testHostWithPrivateDirs()
    info( 'Done.\n')



