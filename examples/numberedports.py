#!/usr/bin/python

"""
Create a network with 5 hosts, numbered 1-4 and 9. 
"""

from mininet.net import Mininet
from mininet.node import Controller
from mininet.cli import CLI
from mininet.log import setLogLevel, info
#from mininet.topo import Topo
from mininet.node import Node

def validatePort( self, intf ):
    "Validate intf's OF port number"
    ofport = int( self.cmd( 'ovs-vsctl get Interface', intf,
                          'ofport' ) )
    if ofport != self.ports[ intf ]:
        warn( 'WARNING: ofport for', intf, 'is actually', ofport,
              '\n' )
        return 0
    else:
        return 1

def net():

    "Create a network with 5 hosts."

    net = Mininet( controller=Controller )

    info( '*** Adding controller\n' )
    net.addController( 'c0' )

    info( '*** Adding hosts\n' )
    h1 = net.addHost( 'h1', ip='10.0.0.1' )
    h2 = net.addHost( 'h2', ip='10.0.0.2' )
    h3 = net.addHost( 'h3', ip='10.0.0.3' )
    h4 = net.addHost( 'h4', ip='10.0.0.4' )
    h5 = net.addHost( 'h5', ip='10.0.0.5' )

    info( '*** Adding switch\n' )
    s1 = net.addSwitch( 's1' )

    info( '*** Creating links\n' )
    net.addLink( h1, s1 )
    net.addLink( h2, s1 )
    net.addLink( h3, s1 )
    net.addLink( h4, s1 )
    net.addLink( h5, s1, port1 = 1, port2 = 9 )

    root = Node( 'root', inNamespace=False )
    info( '*** Starting network\n' )
    net.start()
    #info( s1.intfs, "\n" )
    # print the interfaces, their port numbers, and the port requests
    info( '\n*** printing and validating the ports running on each interface\n' )
    for intfs in s1.intfList():
        if not intfs.name == "lo":
            info( intfs, ': ', root.cmd( 'ovs-vsctl get Interface', intfs, 'ofport' ) )
            info ( 'Validating ', intfs, '... ' )
            if validatePort( s1, intfs ):
                info( 'Validated.\n' )
    print '\n'
        
    #info( root.cmd( 'ovs-vsctl list interface | grep -A 2 s1 ' ) )
    net.pingAll()
    print '\n'

    info( '*** Stopping network' )
    net.stop()

if __name__ == '__main__':
    setLogLevel( 'info' )
    net()

