"Library of potentially useful topologies for Mininet"

from mininet.topo import Topo, Node

class TreeTopo( Topo ):
    "Topology for a tree network with a given depth and fanout."

    def __init__( self, depth=1, fanout=2 ):
        super( TreeTopo, self ).__init__()
        # Build topology
        self.addTree( 1, depth, fanout )
        # Consider all switches and hosts 'on'
        self.enable_all()

    # It is OK that i is "unused" in the for loop.
    # pylint: disable-msg=W0612

    def addTree( self, n, depth, fanout ):
        """Add a subtree starting with node n.
           returns: last node added"""
        me = n
        isSwitch = depth > 0
        self.add_node( me, Node( is_switch=isSwitch ) )
        if isSwitch:
            for i in range( 0, fanout ):
                child = n + 1
                self.add_edge( me, child )
                n = self.addTree( child, depth - 1, fanout )
        return n

    # pylint: enable-msg=W0612
