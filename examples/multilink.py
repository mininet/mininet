#!/usr/bin/python

"""
This is a simple example that demonstrates multiple links
between nodes.
"""

from mininet.cli import CLI
from mininet.log import setLogLevel
from mininet.net import Mininet
from mininet.topo import Topo

def runMultiLink():
    "Create and run multiple link network"
    topo = simpleMultiLinkTopo( n=2 )
    net = Mininet( topo=topo )
    net.start()
    CLI( net )
    net.stop()

class simpleMultiLinkTopo( Topo ):
    "Simple topology with multiple links"

    def __init__( self, n, **kwargs ):
        Topo.__init__( self, **kwargs )

        h1, h2 = self.addHost( 'h1' ), self.addHost( 'h2' )
        s1 = self.addSwitch( 's1' )

        for _ in range( n ):
            self.addLink( s1, h1 )
            self.addLink( s1, h2 )

if __name__ == '__main__':
    setLogLevel( 'info' )
    runMultiLink()
