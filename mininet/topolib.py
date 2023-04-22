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

    def build( self, x, y, n=1 ):
        """x: dimension of torus in x-direction
           y: dimension of torus in y-direction
           n: number of hosts per switch"""
        if x < 3 or y < 3:
            raise Exception( 'Please use 3x3 or greater for compatibility '
                             'with 2.1' )
        if n == 1:
            def genHostName( loc, _k ):
                return 'h%s' % ( loc )
        else:
            def genHostName( loc, k ):
                return 'h%sx%d' % ( loc, k )

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
            for j in range( 0, y ):
                sw1 = switches[ i, j ]
                sw2 = switches[ i, ( j + 1 ) % y ]
                sw3 = switches[ ( i + 1 ) % x, j ]
                self.addLink( sw1, sw2 )
                self.addLink( sw1, sw3 )

# pylint: enable=arguments-differ
