#!/usr/bin/python

"""
This example creates a multi-controller network from
semi-scratch; note a topo object could also be used and
would be passed into the Mininet() constructor.
"""

from mininet.net import Mininet
from mininet.node import Controller, OVSKernelSwitch
from mininet.cli import CLI
from mininet.log import setLogLevel

Switch = OVSKernelSwitch

def addHost( net, N ):
    "Create host hN and add to net."
    name = 'h%d' % N
    ip = '10.0.0.%d' % N
    return net.addHost( name, ip=ip )

def multiControllerNet():
    "Create a network with multiple controllers."

    net = Mininet( controller=Controller, switch=Switch)

    print "*** Creating controllers"
    c1 = net.addController( 'c1', port=6633 )
    c2 = net.addController( 'c2', port=6634 )

    print "*** Creating switches"
    s1 = net.addSwitch( 's1' )
    s2 = net.addSwitch( 's2' )

    print "*** Creating hosts"
    hosts1 = [ addHost( net, n ) for n in 3, 4 ]
    hosts2 = [ addHost( net, n ) for n in 5, 6 ]

    print "*** Creating links"
    for h in hosts1:
        s1.linkTo( h )
    for h in hosts2:
        s2.linkTo( h )
    s1.linkTo( s2 )

    print "*** Starting network"
    net.build()
    c1.start()
    c2.start()
    s1.start( [ c1 ] )
    s2.start( [ c2 ] )

    print "*** Testing network"
    net.pingAll()

    print "*** Running CLI"
    CLI( net )

    print "*** Stopping network"
    net.stop()

if __name__ == '__main__':
    setLogLevel( 'info' )  # for CLI output
    multiControllerNet()
