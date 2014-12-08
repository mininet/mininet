#!/usr/bin/python

"""
linuxrouter.py: Example network with Linux IP router

This example converts a Node into a router using IP forwarding
already built into Linux.

The topology contains a router with three IP subnets:
 - 192.168.1.0/24 (interface IP: 192.168.1.1)
 - 172.16.0.0/12 (interface IP: 172.16.0.1)
 - 10.0.0.0/8 (interface IP: 10.0.0.1)

 It also contains three hosts, one in each subnet:
 - h1 (IP: 192.168.1.100)
 - h2 (IP: 172.16.0.100)
 - h3 (IP: 10.0.0.100)

 Routing entries can be added to the routing tables of the
 hosts or router using the "ip route add" or "route add" command.
 See the man pages for more details.

"""

from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import Node
from mininet.log import setLogLevel, info
from mininet.cli import CLI

class LinuxRouter( Node ):
    "A Node with IP forwarding enabled."

    def config( self, **params ):
        super( LinuxRouter, self).config( **params )
        # Enable forwarding on the router
        self.cmd( 'sysctl net.ipv4.ip_forward=1' )

    def terminate( self ):
        self.cmd( 'sysctl net.ipv4.ip_forward=0' )
        super( LinuxRouter, self ).terminate()


class NetworkTopo( Topo ):
    "A simple topology of a router with three subnets (one host in each)."

    def build( self, **_opts ):
        router = self.addNode( 'r0', cls=LinuxRouter, ip='192.168.1.1/24' )
        h1 = self.addHost( 'h1', ip='192.168.1.100/24',
                           defaultRoute='via 192.168.1.1' )
        h2 = self.addHost( 'h2', ip='172.16.0.100/12',
                           defaultRoute='via 172.16.0.1' )
        h3 = self.addHost( 'h3', ip='10.0.0.100/8',
                           defaultRoute='via 10.0.0.1' )
        self.addLink( h1, router, intfName2='r0-eth1',
                      params2={ 'ip' : '192.168.1.1/24' } )
        self.addLink( h2, router, intfName2='r0-eth2',
                      params2={ 'ip' : '172.16.0.1/12' } )
        self.addLink( h3, router, intfName2='r0-eth3',
                      params2={ 'ip' : '10.0.0.1/8' } )

def run():
    "Test linux router"
    topo = NetworkTopo()
    net = Mininet( topo=topo, controller=None )  # no controller needed
    net.start()
    info( '*** Routing Table on Router\n' )
    print net[ 'r0' ].cmd( 'route' )
    CLI( net )
    net.stop()

if __name__ == '__main__':
    setLogLevel( 'info' )
    run()
