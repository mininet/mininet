#!/usr/bin/env python
'''@package topo

Network topology creation.

@author Brandon Heller (brandonh@stanford.edu)

This package includes code to represent network topologies.

A Topo object can be a topology database for NOX, can represent a physical
setup for testing, and can even be emulated with the Mininet package.
'''

# BL: we may have to fix compatibility here.
# networkx is also a fairly heavyweight dependency
# from networkx.classes.graph import Graph

from networkx import Graph
from mininet.util import irange, natural, naturalSeq

class Topo(object):
    "Data center network representation for structured multi-trees."

    def __init__(self, hopts=None, sopts=None, lopts=None):
        """Topo object:
           hinfo: default host options
           sopts: default switch options
           lopts: default link options"""
        self.g = Graph()
        self.node_info = {}
        self.link_info = {}  # (src, dst) tuples hash to EdgeInfo objects
        self.hopts = {} if hopts is None else hopts
        self.sopts = {} if sopts is None else sopts
        self.lopts = {} if lopts is None else lopts
        self.ports = {}  # ports[src][dst] is port on src that connects to dst

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
            return (self.ports[src][dst], self.ports[dst][src])

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
    "Linear topology of k switches, with one host per switch."

    def __init__(self, k=2, **opts):
        """Init.
           k: number of switches (and hosts)
           hconf: host configuration options
           lconf: link configuration options"""

        super(LinearTopo, self).__init__(**opts)

        self.k = k

        lastSwitch = None
        for i in irange(1, k):
            host = self.addHost('h%s' % i)
            switch = self.addSwitch('s%s' % i)
            self.addLink( host, switch)
            if lastSwitch:
                self.addLink( switch, lastSwitch)
            lastSwitch = switch
