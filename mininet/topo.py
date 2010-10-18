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
from mininet.node import SWITCH_PORT_BASE

class NodeID(object):
    '''Topo node identifier.'''

    def __init__(self, dpid = None):
        '''Init.

        @param dpid dpid
        '''
        # DPID-compatible hashable identifier: opaque 64-bit unsigned int
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
        return str(self.dpid)

    def ip_str(self):
        '''Name conversion.

        @return ip ip as string
        '''
        hi = (self.dpid & 0xff0000) >> 16
        mid = (self.dpid & 0xff00) >> 8
        lo = self.dpid & 0xff
        return "10.%i.%i.%i" % (hi, mid, lo)


class Node(object):
    '''Node-specific vertex metadata for a Topo object.'''

    def __init__(self, connected = False, admin_on = True,
                 power_on = True, fault = False, is_switch = True):
        '''Init.

        @param connected actively connected to controller
        @param admin_on administratively on or off
        @param power_on powered on or off
        @param fault fault seen on node
        @param is_switch switch or host
        '''
        self.connected = connected
        self.admin_on = admin_on
        self.power_on = power_on
        self.fault = fault
        self.is_switch = is_switch


class Edge(object):
    '''Edge-specific metadata for a StructuredTopo graph.'''

    def __init__(self, admin_on = True, power_on = True, fault = False):
        '''Init.

        @param admin_on administratively on or off; defaults to True
        @param power_on powered on or off; defaults to True
        @param fault fault seen on edge; defaults to False
        '''
        self.admin_on = admin_on
        self.power_on = power_on
        self.fault = fault


class Topo(object):
    '''Data center network representation for structured multi-trees.'''

    def __init__(self):
        '''Create Topo object.

        '''
        self.g = Graph()
        self.node_info = {}  # dpids hash to Node objects
        self.edge_info = {}  # (src_dpid, dst_dpid) tuples hash to Edge objects
        self.ports = {}  # ports[src][dst] is port on src that connects to dst
        self.id_gen = NodeID  # class used to generate dpid

    def add_node(self, dpid, node):
        '''Add Node to graph.

        @param dpid dpid
        @param node Node object
        '''
        self.g.add_node(dpid)
        self.node_info[dpid] = node

    def add_edge(self, src, dst, edge = None):
        '''Add edge (Node, Node) to graph.

        @param src src dpid
        @param dst dst dpid
        @param edge Edge object
        '''
        src, dst = tuple(sorted([src, dst]))
        self.g.add_edge(src, dst)
        if not edge:
            edge = Edge()
        self.edge_info[(src, dst)] = edge
        self.add_port(src, dst)

    def add_port(self, src, dst):
        '''Generate port mapping for new edge.

        @param src source switch DPID
        @param dst destination switch DPID
        '''
        src_base = SWITCH_PORT_BASE if self.is_switch(src) else 0
        dst_base = SWITCH_PORT_BASE if self.is_switch(dst) else 0
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

    def node_enabled(self, dpid):
        '''Is node connected, admin on, powered on, and fault-free?

        @param dpid dpid

        @return bool node is enabled
        '''
        ni = self.node_info[dpid]
        return ni.connected and ni.admin_on and ni.power_on and not ni.fault

    def nodes_enabled(self, dpids, enabled = True):
        '''Return subset of enabled nodes

        @param dpids list of dpids
        @param enabled only return enabled nodes?

        @return dpids filtered list of dpids
        '''
        if enabled:
            return [n for n in dpids if self.node_enabled(n)]
        else:
            return dpids

    def nodes(self, enabled = True):
        '''Return graph nodes.

        @param enabled only return enabled nodes?

        @return dpids list of dpids
        '''
        return self.nodes_enabled(self.g.nodes(), enabled)

    def nodes_str(self, dpids):
        '''Return string of custom-encoded nodes.

        @param dpids list of dpids

        @return str string
        '''
        return [str(self.id_gen(dpid = dpid)) for dpid in dpids]

    def is_switch(self, n):
        '''Returns true if node is a switch.'''
        return self.node_info[n].is_switch

    def switches(self, enabled = True):
        '''Return switches.

        @param enabled only return enabled nodes?

        @return dpids list of dpids
        '''
        nodes = [n for n in self.g.nodes() if self.is_switch(n)]
        return self.nodes_enabled(nodes, enabled)

    def hosts(self, enabled = True):
        '''Return hosts.

        @param enabled only return enabled nodes?

        @return dpids list of dpids
        '''

        def is_host(n):
            '''Returns true if node is a host.'''
            return not self.node_info[n].is_switch

        nodes = [n for n in self.g.nodes() if is_host(n)]
        return self.nodes_enabled(nodes, enabled)

    def edge_enabled(self, edge):
        '''Is edge admin on, powered on, and fault-free?

        @param edge (src, dst) dpid tuple

        @return bool edge is enabled
        '''
        src, dst = edge
        src, dst = tuple(sorted([src, dst]))
        ei = self.edge_info[tuple(sorted([src, dst]))]
        return ei.admin_on and ei.power_on and not ei.fault

    def edges_enabled(self, edges, enabled = True):
        '''Return subset of enabled edges

        @param edges list of edges
        @param enabled only return enabled edges?

        @return edges filtered list of edges
        '''
        if enabled:
            return [e for e in edges if self.edge_enabled(e)]
        else:
            return edges

    def edges(self, enabled = True):
        '''Return edges.

        @param enabled only return enabled edges?

        @return edges list of dpid pairs
        '''
        return self.edges_enabled(self.g.edges(), enabled)

    def edges_str(self, dpid_pairs):
        '''Return string of custom-encoded node pairs.

        @param dpid_pairs list of dpid pairs (src, dst)

        @return str string
        '''
        edges = []
        for pair in dpid_pairs:
            src, dst = pair
            src = str(self.id_gen(dpid = src))
            dst = str(self.id_gen(dpid = dst))
            edges.append((src, dst))
        return edges

    def port(self, src, dst):
        '''Get port number.

        @param src source switch DPID
        @param dst destination switch DPID
        @return tuple (src_port, dst_port):
            src_port: port on source switch leading to the destination switch
            dst_port: port on destination switch leading to the source switch
        '''
        if src in self.ports and dst in self.ports[src]:
            assert dst in self.ports and src in self.ports[dst]
            return (self.ports[src][dst], self.ports[dst][src])

    def enable_edges(self):
        '''Enable all edges in the network graph.

        Set admin on, power on, and fault off.
        '''
        for e in self.g.edges():
            src, dst = e
            ei = self.edge_info[tuple(sorted([src, dst]))]
            ei.admin_on = True
            ei.power_on = True
            ei.fault = False

    def enable_nodes(self):
        '''Enable all nodes in the network graph.

        Set connected on, admin on, power on, and fault off.
        '''
        for node in self.g.nodes():
            ni = self.node_info[node]
            ni.connected = True
            ni.admin_on = True
            ni.power_on = True
            ni.fault = False

    def enable_all(self):
        '''Enable all nodes and edges in the network graph.'''
        self.enable_nodes()
        self.enable_edges()

    def name(self, dpid):
        '''Get string name of node ID.

        @param dpid DPID of host or switch
        @return name_str string name with no dashes
        '''
        return self.id_gen(dpid = dpid).name_str()

    def ip(self, dpid):
        '''Get IP dotted-decimal string of node ID.

        @param dpid DPID of host or switch
        @return ip_str
        '''
        return self.id_gen(dpid = dpid).ip_str()


class SingleSwitchTopo(Topo):
    '''Single switch connected to k hosts.'''

    def __init__(self, k = 2, enable_all = True):
        '''Init.

        @param k number of hosts
        @param enable_all enables all nodes and switches?
        '''
        super(SingleSwitchTopo, self).__init__()

        self.k = k

        self.add_node(1, Node())
        hosts = range(2, k + 2)
        for h in hosts:
            self.add_node(h, Node(is_switch = False))
            self.add_edge(h, 1, Edge())

        if enable_all:
            self.enable_all()


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
    '''Linear topology of k switches, with one host per switch.'''

    def __init__(self, k = 2, enable_all = True):
        '''Init.

        @param k number of switches (and hosts too)
        @param enable_all enables all nodes and switches?
        '''
        super(LinearTopo, self).__init__()

        self.k = k

        switches = range(1, k + 1)
        for s in switches:
            h = s + k
            self.add_node(s, Node())
            self.add_node(h, Node(is_switch = False))
            self.add_edge(s, h, Edge())
        for s in switches:
            if s != k:
                self.add_edge(s, s + 1, Edge())

        if enable_all:
            self.enable_all()
