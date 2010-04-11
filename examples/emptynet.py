#!/usr/bin/python

"""
This example shows how to create an empty Mininet() object 
(without a topology object) and add nodes to it manually.
"""

from mininet.net import Mininet
from mininet.node import Controller
from mininet.cli import CLI
from mininet.log import setLogLevel

def emptyNet():

    "Create an empty network and add nodes to it."
    
    net = Mininet( controller=Controller )

    print "*** Adding controller"
    c0 = net.addController( 'c0' )
    
    print "*** Adding hosts"
    h1 = net.addHost( 'h1', ip='10.0.0.1' )
    h2 = net.addHost( 'h2', ip='10.0.0.2' )
    
    print "*** Adding switch"
    s3 = net.addSwitch( 's3' )
    
    print "*** Creating links"
    h1.linkTo( s3 )
    h2.linkTo( s3 )
    
    print "*** Starting network"
    net.build()
    net.start()
    
    print "*** Running CLI"
    setLogLevel( 'info' )
    CLI( net )
    
    print "*** Stopping network"
    net.stop()
    
if __name__ == '__main__':
    emptyNet()
