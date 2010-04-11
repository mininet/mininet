"Library of potentially useful topologies for Mininet"

from mininet.topo import Topo, Node
from mininet.net import Mininet

class TreeTopo( Topo ):
    "Topology for a tree network with a given depth and fanout."

    def __init__( self, depth=1, fanout=2 ):
        super( TreeTopo, self ).__init__()
        # Numbering:  h1..N, sN+1..M
        hostCount = fanout ** depth
        self.hostNum = 1
        self.switchNum = hostCount + 1
        # Build topology
        self.addTree( depth, fanout )
        # Consider all switches and hosts 'on'
        self.enable_all()

    # It is OK that i is "unused" in the for loop.
    # pylint: disable-msg=W0612

    def addTree( self, depth, fanout ):
        """Add a subtree starting with node n.
           returns: last node added"""
        isSwitch = depth > 0
        if isSwitch:
            num = self.switchNum
            self.switchNum += 1
        else:
            num = self.hostNum
            self.hostNum += 1
        self.add_node( num, Node( is_switch=isSwitch ) )
        if isSwitch:
            for i in range( 0, fanout ):
                child = self.addTree( depth - 1, fanout )
                self.add_edge( num, child )
        return num

    # pylint: enable-msg=W0612

def TreeNet( depth=1, fanout=2, **kwargs ):
    "Convenience function for creating tree networks."
    topo = TreeTopo( depth, fanout )
    return Mininet( topo, **kwargs )
