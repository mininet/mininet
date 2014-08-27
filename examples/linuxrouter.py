#!/usr/bin/python

"""
linuxrouter.py: Example network with Linux IP router
 

"""

from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import Node
from mininet.log import setLogLevel
from mininet.cli import CLI
from mininet.util import irange

class Router( Node ):

    def config( self, **params ):
        super( Router, self).config( **params )
        # Enable forwarding on the router
        self.cmd( 'sysctl net.ipv4.ip_forward=1' )

    def terminate( self ):
        self.cmd( 'sysctl net.ipv4.ip_forward=0' )
        super( Router, self ).terminate()


class NetworkTopo(Topo):
    def __init__(self, n=2, h=1, **opts):
        Topo.__init__(self, **opts)

        router = self.addNode('r0', cls=Router, ip='192.168.1.1/24')
        h1 = self.addHost('h1', ip='192.168.1.100/8', defaultRoute='via 192.168.1.1')
        h2 = self.addHost('h2', ip='172.16.0.100/8', defaultRoute='via 172.16.0.1')
        h3 = self.addHost('h3', ip='10.0.0.100/24', defaultRoute='via 10.0.0.1')
        self.addLink(h1, router, intfName2='r0-eth1', params2={ 'ip' : '192.168.1.1/24' })
        self.addLink(h2, router, intfName2='r0-eth2', params2={ 'ip' : '172.16.0.1/24' })
        self.addLink(h3, router, intfName2='r0-eth3', params2={ 'ip' : '10.0.0.1/24' })

def run():
    topo = NetworkTopo()
    net = Mininet(topo=topo)
    net.start()
    CLI(net)
    net.stop()

if __name__ == '__main__':
    setLogLevel('info')
    run()
