#!/usr/bin/env python
'''@package topo

Network topology creation.

@author Brandon Heller (brandonh@stanford.edu)

This package includes code to represent network topologies.

A Topo object can be a topology database for NOX, can represent a physical
setup for testing, and can even be emulated with the Mininet package.
'''

from mininet.util import irange, natural, naturalSeq

class NodeID(object):
    '''Topo node identifier.'''
    sdpidlist = []

    def __init__(self, dpid = None, nodetype=None, name = None):
        '''Init.

        @param dpid dpid
        '''
        # DPID-compatible hashable identifier: opaque 64-bit unsigned int
        self.nodetype = nodetype
        if name:
            self.name = name
            self.nodetype = name[0]
            if self.nodetype == 'h':
                self.dpid = int(name[1:]) + max(self.sdpidlist)
            else:
                self.dpid = int(name[1:])
        elif nodetype == 's':
            self.name = self.nodetype + str(dpid)
            self.dpid = dpid
            self.sdpidlist.append(dpid)
        elif dpid not in self.sdpidlist:
            self.nodetype = 'h'
            self.name = self.nodetype + str(dpid - max(self.sdpidlist))
            self.dpid = dpid
        else:
            self.nodetype = 's'
            self.name = self.nodetype + str(dpid)
            self.dpid = dpid

    def __str__(self):
        '''String conversion.

        @return str dpid as string
        '''
        return str(self.dpid)

    def name_str(self):
        '''Name conversion.

        @return name name as string
        '''
        if (self.nodetype == 'h'):
            return self.nodetype + str(self.dpid - max(self.sdpidlist))
        else:
            return self.nodetype + str(self.dpid)

    def mac_str(self):
        '''Return MAC string'''
        return "00:00:00:00:00:%02x" % (self.dpid)

    def ip_str(self):
        '''Name conversion.

        @return ip ip as string
        '''
        #hi = (self.dpid & 0xff0000) >> 16
        #mid = (self.dpid & 0xff00) >> 8
        #lo = self.dpid & 0xff
        #return "10.%i.%i.%i" % (hi, mid, lo)
        return "10.0.0.%i" % self.dpid

#Borrowed from ripl/ripl/dctopo.py
class StructuredNodeSpec(object):
    '''Layer-specific vertex metadata for a StructuredTopo graph.'''

    def __init__(self, up_total, down_total, up_speed, down_speed,
                 type_str = None):
        '''Init.

        @param up_total number of up links
        @param down_total number of down links
        @param up_speed speed in Gbps of up links
        @param down_speed speed in Gbps of down links
        @param type_str string; model of switch or server
        '''
        self.up_total = up_total
        self.down_total = down_total
        self.up_speed = up_speed
        self.down_speed = down_speed
        self.type_str = type_str


class StructuredEdgeSpec(object):
    '''Static edge metadata for a StructuredTopo graph.'''

    def __init__(self, speed = 1.0):
        '''Init.

        @param speed bandwidth in Gbps
        '''
        self.speed = speed


class MultiGraph( object ):
    "Utility class to track nodes and edges - replaces networkx.Graph"

    def __init__( self ):
        self.data = {}

    def add_node( self, node ):
        "Add node to graph"
        self.data.setdefault( node, [] )

    def add_edge( self, src, dest ):
        "Add edge to graph"
        #src, dest = sorted( ( src, dest ) )
        self.add_node( src )
        self.add_node( dest )
        self.data[ src ].append( dest )
        self.data[ dest ].append( src )

    def nodes( self ):
        "Return list of graph nodes"
        return self.data.keys()

    def edges( self ):
        "Iterator: return graph edges"
        for src in self.data.keys():
            for dest in self.data[ src ]:
                if src <= dest:
                    yield ( src, dest )

    def __getitem__( self, node ):
        "Return link dict for the given node"
        return self.data[node]


class Topo(object):
    "Data center network representation for structured multi-trees."

    def __init__(self, *args, **params):
        """Topo object. 
           Optional named parameters:
           hinfo: default host options
           sopts: default switch options
           lopts: default link options
           calls build()"""
        self.g = MultiGraph()
        self.node_info = {}
        self.link_info = {}  # (src, dst) tuples hash to EdgeInfo objects
        self.hopts = params.pop( 'hopts', {} )
        self.sopts = params.pop( 'sopts', {} )
        self.lopts = params.pop( 'lopts', {} )
        self.ports = {}  # ports[src][dst] is port on src that connects to dst
        self.build( *args, **params )

    def build( self, *args, **params ):
        "Override this method to build your topology."
        pass

    def addNode(self, name, **opts):
        """Add Node to graph.
           name: name
           opts: node options
           returns: node name"""
        self.g.add_node(name)
        self.node_info[name] = opts
        return name

    def addHost(self, name, **opts):
        """Convenience method: Add host to graph.
           name: host name
           opts: host options
           returns: host name"""
        if not opts and self.hopts:
            opts = self.hopts
        return self.addNode(name, **opts)

    def addSwitch(self, name, **opts):
        """Convenience method: Add switch to graph.
           name: switch name
           opts: switch options
           returns: switch name"""
        if not opts and self.sopts:
            opts = self.sopts
        result = self.addNode(name, isSwitch=True, **opts)
        return result

    def addLink(self, node1, node2, port1=None, port2=None,
                **opts):
        """node1, node2: nodes to link together
           port1, port2: ports (optional)
           opts: link options (optional)
           returns: link info key"""
        if not opts and self.lopts:
            opts = self.lopts
        self.addPort(node1, node2, port1, port2)
        key = tuple(self.sorted([node1, node2]))
        self.link_info[key] = opts
        self.g.add_edge(*key)
        return key

    def addPort(self, src, dst, sport=None, dport=None):
        '''Generate port mapping for new edge.
        @param src source switch name
        @param dst destination switch name
        '''
        self.ports.setdefault(src, {})
        self.ports.setdefault(dst, {})
        # New port: number of outlinks + base
        src_base = 1 if self.isSwitch(src) else 0
        dst_base = 1 if self.isSwitch(dst) else 0
        if sport is None:
            sport = len(self.ports[src]) + src_base
        if dport is None:
            dport = len(self.ports[dst]) + dst_base
        self.ports[src][dst] = sport
        self.ports[dst][src] = dport

    def nodes(self, sort=True):
        "Return nodes in graph"
        if sort:
            return self.sorted( self.g.nodes() )
        else:
            return self.g.nodes()

    def isSwitch(self, n):
        '''Returns true if node is a switch.'''
        info = self.node_info[n]
        return info and info.get('isSwitch', False)

    def switches(self, sort=True):
        '''Return switches.
        sort: sort switches alphabetically
        @return dpids list of dpids
        '''
        return [n for n in self.nodes(sort) if self.isSwitch(n)]

    def hosts(self, sort=True):
        '''Return hosts.
        sort: sort hosts alphabetically
        @return dpids list of dpids
        '''
        return [n for n in self.nodes(sort) if not self.isSwitch(n)]

    def links(self, sort=True):
        '''Return links.
        sort: sort links alphabetically
        @return links list of name pairs
        '''
        if not sort:
            return self.g.edges()
        else:
            links = [tuple(self.sorted(e)) for e in self.g.edges()]
            return sorted( links, key=naturalSeq )

    def port(self, src, dst):
        '''Get port number.

        @param src source switch name
        @param dst destination switch name
        @return tuple (src_port, dst_port):
            src_port: port on source switch leading to the destination switch
            dst_port: port on destination switch leading to the source switch
        '''
        if src in self.ports and dst in self.ports[src]:
            assert dst in self.ports and src in self.ports[dst]
            return self.ports[src][dst], self.ports[dst][src]

    def linkInfo( self, src, dst ):
        "Return link metadata"
        src, dst = self.sorted([src, dst])
        return self.link_info[(src, dst)]

    def setlinkInfo( self, src, dst, info ):
        "Set link metadata"
        src, dst = self.sorted([src, dst])
        self.link_info[(src, dst)] = info

    def nodeInfo( self, name ):
        "Return metadata (dict) for node"
        info = self.node_info[ name ]
        return info if info is not None else {}

    def setNodeInfo( self, name, info ):
        "Set metadata (dict) for node"
        self.node_info[ name ] = info

    @staticmethod
    def sorted( items ):
        "Items sorted in natural (i.e. alphabetical) order"
        return sorted(items, key=natural)

class SingleSwitchTopo(Topo):
    '''Single switch connected to k hosts.'''

    def __init__(self, k=2, **opts):
        '''Init.

        @param k number of hosts
        @param enable_all enables all nodes and switches?
        '''
        super(SingleSwitchTopo, self).__init__(**opts)

        self.k = k

        switch = self.addSwitch('s1')
        for h in irange(1, k):
            host = self.addHost('h%s' % h)
            self.addLink(host, switch)


class SingleSwitchReversedTopo(Topo):
    '''Single switch connected to k hosts, with reversed ports.

    The lowest-numbered host is connected to the highest-numbered port.

    Useful to verify that Mininet properly handles custom port numberings.
    '''
    def __init__(self, k=2, **opts):
        '''Init.

        @param k number of hosts
        @param enable_all enables all nodes and switches?
        '''
        super(SingleSwitchReversedTopo, self).__init__(**opts)
        self.k = k
        switch = self.addSwitch('s1')
        for h in irange(1, k):
            host = self.addHost('h%s' % h)
            self.addLink(host, switch,
                         port1=0, port2=(k - h + 1))

class LinearTopo(Topo):
    "Linear topology of k switches, with n hosts per switch."

    def __init__(self, k=2, n=1, **opts):
        """Init.
           k: number of switches
           n: number of hosts per switch
           hconf: host configuration options
           lconf: link configuration options"""

        super(LinearTopo, self).__init__(**opts)

        self.k = k
        self.n = n

        if n == 1:
            genHostName = lambda i, j: 'h%s' % i
        else:
            genHostName = lambda i, j: 'h%ss%d' % (j, i)


        lastSwitch = None
        for i in irange(1, k):
            # Add switch
            switch = self.addSwitch('s%s' % i)
            # Add hosts to switch
            for j in irange(1, n):
                host = self.addHost(genHostName(i, j))
                self.addLink(host, switch)
            # Connect switch to previous
            if lastSwitch:
                self.addLink(switch, lastSwitch)
            lastSwitch = switch

class StructuredTopo(Topo):
    '''Data center network representation for structured multi-trees.'''

    def __init__(self, node_specs, edge_specs):
        '''Create StructuredTopo object.

        @param node_specs list of StructuredNodeSpec objects, one per layer
        @param edge_specs list of StructuredEdgeSpec objects for down-links,
            one per layer
        '''
        super(StructuredTopo, self).__init__()
        self.node_specs = node_specs
        self.edge_specs = edge_specs

    def def_nopts(self, layer):
        '''Return default dict for a structured topo.

        @param layer layer of node
        @return d dict with layer key/val pair, plus anything else (later)
        '''
        return {'layer': layer}

    def layer(self, name):
        '''Return layer of a node

        @param name name of switch
        @return layer layer of switch
        '''
        return self.node_info[name]['layer']

    def isPortUp(self, port):
        ''' Returns whether port is facing up or down

        @param port port number
        @return portUp boolean is port facing up?
        '''
        return port % 2 == PORT_BASE

    def layer_nodes(self, layer):
        '''Return nodes at a provided layer.

        @param layer layer
        @return names list of names
        '''
        def is_layer(n):
            '''Returns true if node is at layer.'''
            return self.layer(n) == layer

        nodes = [n for n in self.g.nodes() if is_layer(n)]
        return nodes

    def up_nodes(self, name):
        '''Return edges one layer higher (closer to core).

        @param name name

        @return names list of names
        '''
        layer = self.layer(name) - 1
        nodes = [n for n in self.g[name] if self.layer(n) == layer]
        return nodes

    def down_nodes(self, name):
        '''Return edges one layer higher (closer to hosts).

        @param name name
        @return names list of names
        '''
        layer = self.layer(name) + 1
        nodes = [n for n in self.g[name] if self.layer(n) == layer]
        return nodes

    def up_edges(self, name):
        '''Return edges one layer higher (closer to core).

        @param name name
        @return up_edges list of name pairs
        '''
        edges = [(name, n) for n in self.up_nodes(name)]
        return edges

    def down_edges(self, name):
        '''Return edges one layer lower (closer to hosts).

        @param name name
        @return down_edges list of name pairs
        '''
        edges = [(name, n) for n in self.down_nodes(name)]
        return edges
