"Library of potentially useful topologies for Mininet"

from mininet.topo import Topo
from mininet.net import Mininet

# The build() method is expected to do this:
# pylint: disable=arguments-differ

class TreeTopo( Topo ):
    "Topology for a tree network with a given depth and fanout."

    def build( self, depth=1, fanout=2 ):
        # Numbering:  h1..N, s1..M
        self.hostNum = 1
        self.switchNum = 1
        # Build topology
        self.addTree( depth, fanout )

    def addTree( self, depth, fanout ):
        """Add a subtree starting with node n.
           returns: last node added"""
        isSwitch = depth > 0
        if isSwitch:
            node = self.addSwitch( 's%s' % self.switchNum )
            self.switchNum += 1
            for _ in range( fanout ):
                child = self.addTree( depth - 1, fanout )
                self.addLink( node, child )
        else:
            node = self.addHost( 'h%s' % self.hostNum )
            self.hostNum += 1
        return node


def TreeNet( depth=1, fanout=2, **kwargs ):
    "Convenience function for creating tree networks."
    topo = TreeTopo( depth, fanout )
    return Mininet( topo, **kwargs )


class TorusTopo( Topo ):
    """2-D Torus topology
       WARNING: this topology has LOOPS and WILL NOT WORK
       with the default controller or any Ethernet bridge
       without STP turned on! It can be used with STP, e.g.:
       # mn --topo torus,3,3 --switch lxbr,stp=1 --test pingall"""

    def build( self, x, y, n=1, wrap=True ):
        """x: number of switches per row
           y: number of rows
           n: number of hosts per switch
           wrap: torus rather than grid? (True)"""
        if x < 3 or y < 3:
            raise Exception( 'Please use 3x3 or greater for compatibility '
                             'with 2.1' )
        if n == 1:
            genHostName = lambda loc, k: 'h%s' % ( loc )
        else:
            genHostName = lambda loc, k: 'h%sx%d' % ( loc, k )

        hosts, switches, dpid = {}, {}, 0
        # Create and wire interior
        for i in range( 0, x ):
            for j in range( 0, y ):
                loc = '%dx%d' % ( i + 1, j + 1 )
                # dpid cannot be zero for OVS
                dpid = ( i + 1 ) * 256 + ( j + 1 )
                switch = switches[ i, j ] = self.addSwitch(
                    's' + loc, dpid='%x' % dpid )
                for k in range( 0, n ):
                    host = hosts[ i, j, k ] = self.addHost(
                        genHostName( loc, k + 1 ) )
                    self.addLink( host, switch )
        # Connect switches
        for i in range( 0, x ):
            for j in range( 0, y):
                sw = switches[ i, j ]
                right = switches[ ( i + 1 ) % x, j ]
                down = switches[ i, ( j + 1 ) % y ]
                if wrap or i + 1 < x:
                    self.addLink( sw, right )
                if wrap or j + 1 < y:
                    self.addLink( sw, down )


class GridTopo( TorusTopo ):
    """2-D Grid topology
       WARNING: this topology has LOOPS and WILL NOT WORK
       with the default controller or any Ethernet bridge
       without STP turned on! It can be used with STP, e.g.:
       # mn --topo grid,3,3 --switch lxbr,stp=1 --test pingall"""

    def build( self, x, y, n=1, wrap=False ):
        """x: number of switches per row
           y: number of rows
           n: number of hosts per switch
           wrap: torus rather than grid (False)"""
        super( GridTopo, self ).build( x, y, n, wrap )


topos = { 'tree': TreeTopo,
          'torus': TorusTopo,
          'grid': GridTopo }

# pylint: enable=arguments-differ
