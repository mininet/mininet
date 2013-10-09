#!/usr/bin/python

"""
Simple example of Mobility with Mininet
(aka enough rope to hang yourself.)

We move a host from s1 to s2, s2 to s3,
and then back to s1.

Gotchas:

1. The interfaces are not renamed; this
   means that s1-eth1 will show up on other
   switches.

2. The reference controller doesn't support
   mobility, so we need to flush the switch
   flow tables.

3. The port numbers reported by the switch
   may not match the actual OpenFlow port
   numbers used by OVS.

Good luck!
"""

from mininet.net import Mininet
from mininet.node import OVSSwitch, Controller
from mininet.topo import LinearTopo
from mininet.cli import CLI
from mininet.util import dumpNetConnections
from time import sleep

class MobilitySwitch( OVSSwitch ):
    "Switch that can delete interfaces"

    def delIntf( self, intf ):
        "Remove an interface"
        port = self.ports[ intf ]
        del self.ports[ intf ]
        del self.intfs[ port ]
        del self.nameToIntf[ intf.name ]
        self.detach( intf )


def printConnections( switches ):
    "Compactly print connected nodes to each switch"
    for sw in switches:
        print '%s:' % sw,
        for intf in sw.intfList():
            link = intf.link
            if link:
                intfs = [ link.intf1, link.intf2 ]
                if intfs[ 0 ].node != sw:
                    intfs.reverse()
                local, remote = intfs
                print remote.node,
        print


def mobilityTest():
    "A simple test of mobility"
    print '* Simple mobility test'
    net = Mininet( topo=LinearTopo( 3 ), switch=MobilitySwitch )
    net.start()
    print '* Starting network:'
    printConnections( net.switches )
    net.pingAll()
    print '* Identifying switch interface for h1'
    h1, s1 = net.get( 'h1', 's1' )
    hintf, sintf = h1.connectionsTo( s1 )[ 0 ]
    last = s1
    for s in 2, 3, 1:
        next = net['s%d' % s ]
        print '* Moving', sintf, 'from', last, 'to', next
        last.detach( sintf )
        last.delIntf( sintf )
        next.attach( sintf )
        next.addIntf( sintf )
        sintf.node = next
        print '* Clearing out old flows'
        for sw in net.switches:
            sw.dpctl( 'del-flows' )
        print '* New network:'
        printConnections( net.switches )
        print '* Testing connectivity:'
        net.pingAll()
        last = next
    net.stop()

if __name__ == '__main__':
    mobilityTest()

