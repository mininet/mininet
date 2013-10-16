#!/usr/bin/python

"""
Simple example of Mobility with Mininet
(aka enough rope to hang yourself.)

We move a host from s1 to s2, s2 to s3, and then back to s1.

Gotchas:

The reference controller doesn't support mobility, so we need to
manually flush the switch flow tables!

Good luck!
"""

from mininet.net import Mininet
from mininet.node import OVSSwitch, Controller
from mininet.topo import LinearTopo
from mininet.cli import CLI
from mininet.util import dumpNetConnections
from mininet.log import output
from time import sleep


class MobilitySwitch( OVSSwitch ):
    "Switch that can reattach and rename interfaces"

    def delIntf( self, intf ):
        "Remove (and detach) an interface"
        port = self.ports[ intf ]
        del self.ports[ intf ]
        del self.intfs[ port ]
        del self.nameToIntf[ intf.name ]

    def addIntf( self, intf, rename=True, **kwargs ):
        "Add (and reparent) an interface"
        OVSSwitch.addIntf( self, intf, **kwargs )
        intf.node = self
        if rename:
            self.renameIntf( intf )

    def renameIntf( self, intf, newname='' ):
        "Rename an interface (to its canonical name)"
        intf.ifconfig( 'down' )
        if not newname:
            newname = '%s-eth%d' % ( self.name, self.ports[ intf ] )
        intf.cmd( 'ip link set', intf, 'name', newname )
        del self.nameToIntf[ intf.name ]
        intf.name = newname
        self.nameToIntf[ intf.name ] = intf
        intf.ifconfig( 'up' )

    def validatePort( self, intf ):
        "Validate intf's OF port number"
        ofport = int( intf.cmd( 'ovs-vsctl get Interface', intf,
                              'ofport' ) )
        assert ofport == self.ports[ intf ]

    def moveIntf( self, intf, switch, rename=True ):
        "Move one of our interfaces to another switch"
        self.detach( intf )
        self.delIntf( intf )
        switch.addIntf( intf, rename=True )
        switch.attach( intf )
        switch.validatePort( intf )


def printConnections( switches ):
    "Compactly print connected nodes to each switch"
    for sw in switches:
        output( '%s: ' % sw )
        for intf in sw.intfList():
            link = intf.link
            if link:
                intf1, intf2 = link.intf1, link.intf2
                remote = intf1 if intf1.node != sw else intf2
                output( '%s(%s) ' % ( remote.node, sw.ports[ intf ] ) )
        output( '\n' )


def moveHost( host, oldSwitch, newSwitch ):
    "Move a host from old switch to new switch"
    hintf, sintf = host.connectionsTo( oldSwitch )[ 0 ]
    oldSwitch.moveIntf( sintf, newSwitch )
    return hintf, sintf


def mobilityTest():
    "A simple test of mobility"
    print '* Simple mobility test'
    net = Mininet( topo=LinearTopo( 3 ), switch=MobilitySwitch )
    net.start()
    print '* Starting network:'
    printConnections( net.switches )
    net.pingAll()
    print '* Identifying switch interface for h1'
    h1, last = net.get( 'h1', 's1' )
    for s in 2, 3, 1:
        next = net[ 's%d' % s ]
        print '* Moving', h1, 'from', last, 'to', next
        hintf, sintf = moveHost( h1, last, next )
        print '*', hintf, 'is now connected to', sintf
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

