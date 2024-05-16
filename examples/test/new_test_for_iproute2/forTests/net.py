#!/usr/bin/env python
from mininet.net import Mininet
from mininet.log import setLogLevel, info
from mininet.cli import CLI


def net():

    net = Mininet()
    c0 = net.addController()
    s1 = net.addSwitch( 's1' )
    h1 = net.addHost( 'h1', ip='0.0.0.0/0' )
    h2 = net.addHost( 'h2', ip='0.0.0.0/0' )
    net.addLink( h1, s1 )
    net.addLink( h2, s1 )  
    net.start()
    CLI( net )
    net.stop()
    
if __name__ == '__main__':
    setLogLevel( 'info' )
    net()
