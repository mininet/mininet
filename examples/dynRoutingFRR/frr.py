#!/usr/bin/env python
"""                                                                            
frr.py: Example of a network with two linked FRR routers running bgpd. Each
        one is connected to a host.
                                                      
This example converts a Node into a BGP router using IP forwarding already 
built into Linux and FRR.
The FRR version tested here is 6.0.3-1~ubuntu14.04.1.
For the example to work properly, configuration files for zebra and bgpd are
provided in a separate directory (r1 & r2).

The example topology:

 h1 --10.0.1/24-- eth0|r1|eth1 --10.0.3/24-- eth1|r2|eth0 --10.0.2/24-- h2

FRR must be installed on the host before. You may need to adapt the binaries
path.

At the CLI prompt, you can xterm to the routers and show the prefixe learned,
see run() comments.
"""

import time
import os
import sys

from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import Node
from mininet.log import setLogLevel, info
from mininet.cli import CLI

CWD = os.path.dirname( os.path.realpath( __file__ ) )
sys.path.append( os.path.join( CWD, "../" ) )

class LinuxRouter( Node ):
    "A Node with IP forwarding enabled."

    def config( self, **params ):
        super( LinuxRouter, self).config( **params )

        # Enable forwarding on the router
        self.cmd( 'sysctl net.ipv4.ip_forward=1' )
        # Enable loose reverse path filtering
        self.cmd( 'sysctl net.ipv4.conf.all.rp_filter=2' )

        zebra = "/usr/lib/frr/zebra"
        bgpd = "/usr/lib/frr/bgpd"
        ospfd = "/usr/lib/frr/ospfd"
        staticd = "/usr/lib/frr/staticd"

        # do some mounts bind to make vtysh and the daemons working
        r = self.name
        self.cmd( "mkdir /tmp/{} && chown frr /tmp/{}".format(r, r) )
        self.cmd( "mount --bind /tmp/{} /var/run/frr".format(r) )
        self.cmd( "mount --bind {} /etc/frr".format(r) )

        # Run the daemons
        self.cmd( "{} -f {}/zebra.conf -d \
            > /tmp/{}/zebra.log 2>&1".format(zebra, r, r) )
        self.waitOutput()

        self.cmd( "{} -f {}/bgpd.conf -d  \
            > /tmp/{}/bgpd.log 2>&1".format(bgpd, r, r) )
        self.waitOutput()

        self.cmd( "{} -f {}/staticd.conf -d \
            > /tmp/{}/staticd.log 2>&1".format(staticd, r, r) )
        self.waitOutput()

    def terminate( self ): 
        r = self.name
        self.cmd( 'sysctl net.ipv4.ip_forward=0' )
        self.cmd( 'sysctl net.ipv4.conf.all.rp_filter=0' )

        self.cmd( "killall bgpd staticd zebra" )
        self.cmd( "umount /var/run/frr" )
        self.cmd( "umount /etc/frr" )
        self.cmd( "rm -fr /tmp/{}".format(r) )
        super( LinuxRouter, self ).terminate()

class NetworkTopo( Topo ):
    "Two FRR routers linked together and each to a host"

    def build( self, **_opts ):

        # We declare the routers
        # The ip indicated here is for the first free port, so xx-eth0
        router1 = self.addNode( 'r1', cls=LinuxRouter, ip='10.0.1.254/24' )
        router2 = self.addNode( 'r2', cls=LinuxRouter, ip='10.0.2.254/24' )

        # We declare the hosts
        h1 = self.addHost( 'h1', ip='10.0.1.1/24', 
                            defaultRoute='via 10.0.1.254')
        h2 = self.addHost( 'h2', ip='10.0.2.2/24', 
                            defaultRoute='via 10.0.2.254')

        # We link the hosts to their routers
        self.addLink( h1, router1, intfName2='r1-eth0' )
        self.addLink( h2, router2, intfName2='r2-eth0' )

        # we link the routers together and set the ip of each new port used
        self.addLink( router1, router2, 
                    intfName1='r1-eth1', params1={'ip':'10.0.3.1/24'}, 
                    intfName2='r2-eth1', params2={'ip':'10.0.3.2/24'}  )


def run():
    """ 
    Run the topology declared above.
    Here we must launch the zebra and bgpd and do some hacking to make
    everything working fine (ex. the mount bind).

    At the CLI prompt do 

Mininet> xterm r1

then :

13:36:55 root @ mininet-vm [~/mininet/examples/mine] 
# vtysh 

Hello, this is FRRouting (version 6.0.3).
Copyright 1996-2005 Kunihiro Ishiguro, et al.

mininet-vm# 
mininet-vm# sh ip route 
Codes: K - kernel route, C - connected, S - static, R - RIP,
       O - OSPF, I - IS-IS, B - BGP, E - EIGRP, N - NHRP,
       T - Table, v - VNC, V - VNC-Direct, A - Babel, D - SHARP,
       F - PBR,
       > - selected route, * - FIB route

C>* 10.0.1.0/24 is directly connected, r1-eth0, 00:00:29
B>* 10.0.2.0/24 [20/0] via 10.0.3.2, r1-eth1, 00:00:24
C>* 10.0.3.0/24 is directly connected, r1-eth1, 00:00:30
mininet-vm#

The B>* shows the remote prefix learned from r2 router by bgpd

    """

    topo = NetworkTopo()    
    net = Mininet( topo=topo ) 
    net.start()

    CLI( net )

    net.stop()

if __name__ == '__main__':
    setLogLevel( 'info' )
    run()
