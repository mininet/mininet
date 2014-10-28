#!/usr/bin/env python
"""@package topo

Network topology creation.

@author Brandon Heller (brandonh@stanford.edu)

This package includes code to represent network topologies.

A Topo object can be a topology database for NOX, can represent a physical
setup for testing, and can even be emulated with the Mininet package.
"""

from mininet.util import irange, natural, naturalSeq

class MultiGraph( object ):
    "Utility class to track nodes and edges - replaces networkx.MultiGraph"

    def __init__( self ):
        self.node = {}
        self.edge = {}
        self.edgeinfo = {}

    def add_node( self, node, attr_dict=None, **attrs):
        """Add node to graph
           attr_dict: attribute dict (optional)
           attrs: more attributes (optional)"""
        attr_dict = {} if attr_dict is None else attr_dict
        attr_dict.update( attrs )
        self.node[ node ] = attr_dict

    def add_edge( self, src, dst, key=None, attr_dict=None, **attrs ):
        """Add edge to graph
           key: optional key
           attr_dict: optional attribute dict"""
        attr_dict = {} if attr_dict is None else attr_dict
        attr_dict.update( attrs )
        self.node.setdefault( src, {} )
        self.node.setdefault( dst, {} )
        self.edge.setdefault( src, {} )
        self.edge.setdefault( dst, {} )
        self.edge[ src ].setdefault( dst, {} )
        entry = self.edge[ dst ][ src ] = self.edge[ src ][ dst ]
        # If no key, pick next ordinal number
        if key is None:
            keys = [ k for k in entry.keys() if type( k ) is int ]
            key = max( [ 0 ] + keys ) + 1
        entry[ key ] = attr_dict
        return key

    def nodes( self, data=False):
        """Return list of graph nodes
           data: return list of ( node, attrs)"""
        return self.node.items() if data else self.node.keys()

    def edges_iter( self, data=False, key=False):
        "Iterator: return graph edges"
        for src, entry in self.edge.iteritems():
            for dst, keys in entry.iteritems():
                if [ src, dst ] != sorted( [ src, dst ] ):
                    # Skip duplicate edges
                    continue
                for k, attrs in keys.iteritems():
                    if data:
                        yield( ( src, dst, attrs ) )
                    elif key:
                        yield( ( src, dst, k ) )
                    else:
                        yield( ( src, dst ) )

    def edges( self, data=False, key=False ):
        "Return list of graph edges"
        return list( self.edges_iter( data=data, key=key ) )


    def __getitem__( self, node ):
        "Return link dict for given src node"
        return self.edge[ node ]

    def __len__( self ):
        "Return the number of nodes"
        return len( self.node )

    def convertTo( self, cls, data=False ):
        """Convert to a new object of networkx.MultiGraph-like class cls
           data: include node and edge data"""
        g = cls()
        g.add_nodes_from( self.nodes( data=data ) )
        g.add_edges_from( self.edges( data=data ) )
        return g


class Topo( object ):
    "Data center network representation for structured multi-trees."

    def __init__( self, *args, **params ):
        """Topo object. 
           Optional named parameters:
           hinfo: default host options
           sopts: default switch options
           lopts: default link options
           calls build()"""
        self.g = MultiGraph()
        self.hopts = params.pop( 'hopts', {} )
        self.sopts = params.pop( 'sopts', {} )
        self.lopts = params.pop( 'lopts', {} )
        self.ports = {}  # ports[src][dst][sport] is port on dst that connects to src
        self.build( *args, **params )

    def build( self, *args, **params ):
        "Override this method to build your topology."
        pass

    def addNode( self, name, **opts ):
        """Add Node to graph.
           name: name
           opts: node options
           returns: node name"""
        self.g.add_node( name, **opts )
        return name

    def addHost( self, name, **opts ):
        """Convenience method: Add host to graph.
           name: host name
           opts: host options
           returns: host name"""
        if not opts and self.hopts:
            opts = self.hopts
        return self.addNode( name, **opts )

    def addSwitch( self, name, **opts ):
        """Convenience method: Add switch to graph.
           name: switch name
           opts: switch options
           returns: switch name"""
        if not opts and self.sopts:
            opts = self.sopts
        result = self.addNode( name, isSwitch=True, **opts )
        return result

    def addLink( self, node1, node2, port1=None, port2=None,
                key=None, **opts ):
        """node1, node2: nodes to link together
           port1, port2: ports (optional)
           opts: link options (optional)
           returns: link info key"""
        if not opts and self.lopts:
            opts = self.lopts
        port1, port2 = self.addPort( node1, node2, port1, port2 )
        opts.update( node1=node1, node2=node2, port1=port1, port2=port2 )
        self.g.add_edge(node1, node2, key, opts )
        return key

    def nodes( self, sort=True ):
        "Return nodes in graph"
        if sort:
            return self.sorted( self.g.nodes() )
        else:
            return self.g.nodes()

    def isSwitch( self, n ):
        "Returns true if node is a switch."
        return self.g.node[ n ].get( 'isSwitch', False )

    def switches( self, sort=True ):
        """Return switches.
           sort: sort switches alphabetically
           returns: dpids list of dpids"""
        return [ n for n in self.nodes( sort ) if self.isSwitch( n ) ]

    def hosts( self, sort=True ):
        """Return hosts.
           sort: sort hosts alphabetically
           returns: list of hosts"""
        return [ n for n in self.nodes( sort ) if not self.isSwitch( n ) ]

    def links( self, sort=True, withInfo=False, withKeys=False ):
        """Return links.
           sort: sort links alphabetically
           withKeys: return key in tuple
           returns: links list of ( src, dst [,key ] )"""
        if not sort:
            return self.g.edges( data=withInfo, key=withKeys )
        else:
            if withInfo:
                links = [ tuple( self.sorted( ( s, d ) ) + [ info ] )
                          for s, d, info in self.g.edges( data=True ) ]
            elif withKeys:
                links = [ tuple( self.sorted( ( s, d ) ) + [ key ] )
                          for s, d, key in self.g.edges( key=True ) ]
            else:
                links = [ tuple ( self.sorted( e ) )
                          for e in self.g.edges() ]
            return self.sorted( links )

    # This legacy port management mechanism is clunky and will probably
    # be removed at some point.

    def addPort( self, src, dst, sport=None, dport=None ):
        """Generate port mapping for new edge.
            src: source switch name
            dst: destination switch name"""
        # Initialize if necessary
        ports = self.ports
        ports.setdefault( src, {} )
        ports.setdefault( dst, {} )
        # New port: number of outlinks + base
        if sport is None:
            src_base = 1 if self.isSwitch( src ) else 0
            sport = len( ports[ src ] ) + src_base
        if dport is None:
            dst_base = 1 if self.isSwitch( dst ) else 0
            dport = len( ports[ dst ] ) + dst_base
        ports[ src ][ sport ] = ( dst, dport )
        ports[ dst ][ dport ] = ( src, sport )
        return sport, dport

    def port( self, src, dst ):
        """Get port numbers.
            src: source switch name
            dst: destination switch name
            sport: optional source port (otherwise use lowest src port)
            returns: tuple (sport, dport), where
                sport = port on source switch leading to the destination switch
                dport = port on destination switch leading to the source switch
            Note that you can also look up ports using linkInfo()"""
        # A bit ugly and slow vs. single-link implementation ;-(
        ports = [ ( sport, entry[ 1 ] )
                  for sport, entry in self.ports[ src ].items()
                  if entry[ 0 ] == dst ]
        return ports if len( ports ) != 1 else ports[ 0 ]

    def _linkEntry( self, src, dst, key=None ):
        "Helper function: return link entry and key"
        entry = self.g[ src ][ dst ]
        if key is None:
            key = min( entry )
        return entry, key
    
    def linkInfo( self, src, dst, key=None ):
        "Return link metadata dict"
        entry, key = self._linkEntry( src, dst, key )
        return entry[ key ]

    def setlinkInfo( self, src, dst, info, key=None ):
        "Set link metadata dict"
        entry, key = self._linkEntry( src, dst, key )
        entry[ key ] = info

    def nodeInfo( self, name ):
        "Return metadata (dict) for node"
        return self.g.node[ name ]

    def setNodeInfo( self, name, info ):
        "Set metadata (dict) for node"
        self.g.node[ name ] = info

    @staticmethod
    def sorted( items ):
        "Items sorted in natural (i.e. alphabetical) order"
        return sorted( items, key=natural )


class SingleSwitchTopo( Topo ):
    "Single switch connected to k hosts."

    def build( self, k=2, **opts ):
        "k: number of hosts"
        self.k = k
        switch = self.addSwitch( 's1' )
        for h in irange( 1, k ):
            host = self.addHost( 'h%s' % h )
            self.addLink( host, switch )


class SingleSwitchReversedTopo( Topo ):
    """Single switch connected to k hosts, with reversed ports.
       The lowest-numbered host is connected to the highest-numbered port.
       Useful to verify that Mininet properly handles custom port numberings."""

    def build( self, k=2 ):
        "k: number of hosts"
        self.k = k
        switch = self.addSwitch( 's1' )
        for h in irange( 1, k ):
            host = self.addHost( 'h%s' % h )
            self.addLink( host, switch,
                          port1=0, port2=( k - h + 1 ) )


class LinearTopo( Topo ):
    "Linear topology of k switches, with n hosts per switch."

    def build( self, k=2, n=1, **opts):
        """k: number of switches
           n: number of hosts per switch"""
        self.k = k
        self.n = n

        if n == 1:
            genHostName = lambda i, j: 'h%s' % i
        else:
            genHostName = lambda i, j: 'h%ss%d' % ( j, i )

        lastSwitch = None
        for i in irange( 1, k ):
            # Add switch
            switch = self.addSwitch( 's%s' % i )
            # Add hosts to switch
            for j in irange( 1, n ):
                host = self.addHost( genHostName( i, j ) )
                self.addLink( host, switch )
            # Connect switch to previous
            if lastSwitch:
                self.addLink( switch, lastSwitch )
            lastSwitch = switch
