"Library of potentially useful topologies for Mininet"

import os
from mininet.topo import Topo
from mininet.net import Mininet
from mininet.utilib import *

class TreeTopo( Topo ):
    "Topology for a tree network with a given depth and fanout."

    def __init__( self, depth=1, fanout=2 ):
        super( TreeTopo, self ).__init__()
        # Numbering:  h1..N, s1..M
        self.hostNum = 1
        self.switchNum = 1
        # Build topology
        if valuefind('multinet') != 0:
            valueupdate('switchalpha')
            valueupdate('hostalpha')
        self.addTree( depth, fanout )

    def addTree( self, depth, fanout ):
        switchalpha = int(valuefind('switchalpha'))
        if isSwitch:
            node = self.addSwitch( 's%s' % chr(switchalpha + 64) + '%s' % self.switchNum )
            self.switchNum += 1
            for _ in range( fanout ):
                child = self.addTree( depth - 1, fanout )
                self.addLink( node, child )
        else:
            node = self.addHost( 'h%s' % chr(switchalpha + 64) + '%s' % self.hostNum )
            self.hostNum += 1
        return node

def TreeNet( depth=1, fanout=2, **kwargs ):
    "Convenience function for creating tree networks."
    topo = TreeTopo( depth, fanout )
    return Mininet( topo, **kwargs )
