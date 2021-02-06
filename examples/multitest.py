#!/usr/bin/env python

"""
This example shows how to create a network and run multiple tests.
For a more complicated test example, see udpbwtest.py.
"""

from mininet.cli import CLI
from mininet.log import lg, info
from mininet.net import Mininet
from mininet.node import OVSKernelSwitch
from mininet.topolib import TreeTopo

def ifconfigTest( net ):
    "Run ifconfig on all hosts in net."
    hosts = net.hosts
    for host in hosts:
        info( host.cmd( 'ifconfig' ) )


if __name__ == '__main__':
    lg.setLogLevel( 'info' )
    info( "*** Initializing Mininet and kernel modules\n" )
    OVSKernelSwitch.setup()
    info( "*** Creating network\n" )
    network = Mininet( TreeTopo( depth=2, fanout=2), switch=OVSKernelSwitch,
                       waitConnected=True )
    info( "*** Starting network\n" )
    network.start()
    info( "*** Running ping test\n" )
    network.pingAll()
    info( "*** Running ifconfig test\n" )
    ifconfigTest( network )
    info( "*** Starting CLI (type 'exit' to exit)\n" )
    CLI( network )
    info( "*** Stopping network\n" )
    network.stop()
