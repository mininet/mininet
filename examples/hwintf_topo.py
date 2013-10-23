#!/usr/bin/python

"""
This example shows how to add an interface (for example a real
hardware interface) to a Mininet topology.
"""

import sys

from mininet.cli import CLI
from mininet.log import setLogLevel, info
from mininet.net import Mininet
from mininet.topo import Topo
from mininet.link import Intf, Link
from mininet.examples.hwintf import checkIntf

class NoneIntf( Intf ):

    "A dummy interface with a blank name that doesn't do any configuration"

    def __init__( self, name, **params ):
        self.name = ''

class HWIntfLink( Link ):

    "A dummy link that doesn't touch either interface"

    def makeIntfPair( cls, intf1, intf2 ):
        pass

    def delete( self ):
        pass

class HWIntfTopo( Topo ):

    "Simple one switch, two host topology with hwintf added to switch"

    def __init__(self, intf, **opts):
        Topo.__init__(self, **opts)

        sw = self.addSwitch( 's1' )
        h1 = self.addHost( 'h1' )
        h2 = self.addHost( 'h2' )
        self.addLink( sw, h1 )
        self.addLink( sw, h2 )
        self.addLink( sw, sw, cls=HWIntfLink, intfName1=intf, cls2=NoneIntf )

def run():
    # Get hwintf from command line args, and verify that it is not used
    intfName = sys.argv[ 1 ] if len( sys.argv ) > 1 else 'eth1'
    checkIntf( intfName )

    topo = HWIntfTopo( intf=intfName )
    net = Mininet( topo=topo )
    net.start()
    CLI( net )
    net.stop()

if __name__ == '__main__':
    setLogLevel( 'info' )
    run()
