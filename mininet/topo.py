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
from mininet.util import netParse, ipStr, irange, natural, naturalSeq

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
        self.sopts = {} if sopts is None else lopts
        self.lopts = {} if lopts is None else lopts
        self.ports = {}  # ports[src][dst] is port on src that connects to dst

    def add_node(self, name, *args, **opts):
        """Add Node to graph.
           add_node('name', dict) <or> add_node('name', **opts)
           name: name
           args: dict of node options 
           opts: node options"""
        self.g.add_node(name)
        if args and type(args[0]) is dict:
            opts = args[0]
        self.node_info[name] = opts
        return name

    def add_host(self, name, *args, **opts):
        """Convenience method: Add host to graph.
           add_host('name', dict) <or> add_host('name', **opts)
           name: name
           args: dict of node options 
           opts: node options"""
        if not opts and self.hopts:
            opts = self.hopts
        return self.add_node(name, *args, **opts)

    def add_switch(self, name, **opts):
        """Convenience method: Add switch to graph.
           add_switch('name', dict) <or> add_switch('name', **opts)
           name: name
           args: dict of node options 
           opts: node options"""
        if not opts and self.sopts:
            opts = self.sopts
        result = self.add_node(name, is_switch=True, **opts)
        return result

    def add_link(self, src, dst, *args, **opts):
        """Add link (Node, Node) to topo.
           add_link(src, dst, dict) <or> add_link(src, dst, **opts)
           src: src name
           dst: dst name
           args: dict of node options
           params: link parameters"""
        src, dst = sorted([src, dst], key=naturalSeq)
        self.g.add_edge(src, dst)
        if args and type(args[0]) is dict:
            opts = args[0]
        if not opts and self.sopts:
            opts = self.sopts
        self.link_info[(src, dst)] = opts
        self.add_port(src, dst)
        return src, dst

    def add_port(self, src, dst):
        '''Generate port mapping for new edge.

        @param src source switch DPID
        @param dst destination switch DPID
        '''
        src_base = 1 if self.is_switch(src) else 0
        dst_base = 1 if self.is_switch(dst) else 0
        if src not in self.ports:
            self.ports[src] = {}
        if dst not in self.ports[src]:
            # num outlinks
            self.ports[src][dst] = len(self.ports[src]) + src_base
        if dst not in self.ports:
            self.ports[dst] = {}
        if src not in self.ports[dst]:
            # num outlinks
            self.ports[dst][src] = len(self.ports[dst]) + dst_base
    
    def nodes(self, sort=True):
        "Return nodes in graph"
        if sort:
            return sorted( self.g.nodes(), key=natural )
        else:
            return self.g.nodes()

    def is_switch(self, n):
        '''Returns true if node is a switch.'''
        info = self.node_info[n]
        return info and info['is_switch']

    def switches(self, sort=True):
        '''Return switches.
        sort: sort switches alphabetically
        @return dpids list of dpids
        '''
        return [n for n in self.nodes(sort) if self.is_switch(n)]

    def hosts(self, sort=True):
        '''Return hosts.
        sort: sort hosts alphabetically
        @return dpids list of dpids
        '''
        return [n for n in self.nodes(sort) if not self.is_switch(n)]

    def links(self, sort=True):
        '''Return links.
        sort: sort links alphabetically
        @return links list of name pairs
        '''
        if not sort:
            return self.g.edges()
        else:
            return sorted( self.g.edges(), key=naturalSeq )

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
        src, dst = sorted((src, dst), key=naturalSeq)
        return self.link_info[(src, dst)]

    def nodeInfo( self, name ):
        "Return metadata (dict) for node"
        info = self.node_info[ name ]
        return info if info is not None else {}

    def setNodeInfo( self, name, info ):
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

        switch = self.add_switch('s1')
        for h in irange(1, k):
            host = self.add_host('h%s' % h)
            self.add_link(host, switch)


class SingleSwitchReversedTopo(SingleSwitchTopo):
    '''Single switch connected to k hosts, with reversed ports.

    The lowest-numbered host is connected to the highest-numbered port.

    Useful to verify that Mininet properly handles custom port numberings.
    '''

    def port(self, src, dst):
        '''Get port number.

        @param src source switch DPID
        @param dst destination switch DPID
        @return tuple (src_port, dst_port):
            src_port: port on source switch leading to the destination switch
            dst_port: port on destination switch leading to the source switch
        '''
        if src == 1:
            if dst in range(2, self.k + 2):
                dst_index = dst - 2
                highest = self.k - 1
                return (highest - dst_index, 0)
            else:
                raise Exception('unexpected dst: %i' % dst)
        elif src in range(2, self.k + 2):
            if dst == 1:
                raise Exception('unexpected dst: %i' % dst)
            else:
                src_index = src - 2
                highest = self.k - 1
                return (0, highest - src_index)


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
            host = self.add_host('h%s' % i)
            switch = self.add_switch('s%s' % i)
            self.add_link( host, switch)
            if lastSwitch:
                self.add_link( switch, lastSwitch)
            lastSwitch = switch
