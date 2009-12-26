#!/usr/bin/env python
'''Starter topologies for Mininet.'''

from ripcord.topo import Topo, StructuredNodeSpec, StructuredNode, Edge
from ripcord.topo import StructuredTopo, StructuredEdgeSpec, NodeID

class TreeTopo(StructuredTopo):
    '''Tree-structured network.'''

    class TreeNodeID(NodeID):
        '''Tree-specific node.'''

        def __init__(self, layer = 0, index = 0, dpid = None):
            '''Create TreeNodeID object from custom params.

            Either (layer, index) or dpid must be passed in.

            @param layer layer
            @param index index within layer
            @param dpid optional dpid
            '''
            if dpid:
                self.layer = (dpid & 0xff0000) >> 16
                self.index = (dpid & 0xffff)
                self.dpid = dpid
            else:
                self.layer = layer
                self.index = index
                self.dpid = (layer << 16) + index

        def __str__(self):
            return "(%i_%i)" % (self.layer, self.index)

        def name_str(self):
            return "%i_%i" % (self.layer, self.index)

        def ip_str(self):
            # add 1; can't have IP addr ending in 0
            index_hi = (self.index & 0xff00) >> 8
            index_lo = self.index & 0xff
            return "10.%i.%i.%i" % (self.layer, index_hi, index_lo)

    def __init__(self, depth = 2, fanout = 2, speed = 1.0, enable_all = True):
        '''Init.

        @param depth number of levels, including host level
        @param fanout
        '''
        node_specs = []
        core = StructuredNodeSpec(0, fanout, None, speed, type_str = 'core')
        node_specs.append(core)
        for i in range(1, depth - 1):
            node = StructuredNodeSpec(1, fanout, speed, speed,
                                      type_str = 'layer' + str(i))
            node_specs.append(node)
        host = StructuredNodeSpec(1, 0, speed, None, type_str = 'host')
        node_specs.append(host)
        edge_specs = [StructuredEdgeSpec(speed)] * (depth - 1)
        super(TreeTopo, self).__init__(node_specs, edge_specs)

        self.depth = depth
        self.fanout = fanout
        self.id_gen = TreeTopo.TreeNodeID

        # create root
        root_id = self.id_gen(0, 0).dpid
        self._add_node(root_id, StructuredNode(0))
        last_layer_ids = [root_id]

        # create lower layers
        for i in range(1, depth):
            current_layer_ids = []
            # start index at 1, as we can't have IP addresses ending in 0
            index = 1
            for last_id in last_layer_ids:
                for j in range(fanout):
                    is_switch = (i < depth - 1)
                    node = StructuredNode(i, is_switch = is_switch)
                    node_id = self.id_gen(i, index).dpid
                    current_layer_ids.append(node_id)
                    self._add_node(node_id, node)
                    self._add_edge(last_id, node_id, Edge())
                    index += 1
            last_layer_ids = current_layer_ids

        if enable_all:
            self.enable_all()

    def port(self, src, dst):
        '''Get port number (optional)

        Note that the topological significance of DPIDs in FatTreeTopo enables
        this function to be implemented statelessly.

        @param src source switch DPID
        @param dst destination switch DPID
        @return tuple (src_port, dst_port):
            src_port: port on source switch leading to the destination switch
            dst_port: port on destination switch leading to the source switch
        '''

        src_layer = self.node_info[src].layer
        dst_layer = self.node_info[dst].layer

        src_id = self.id_gen(dpid = src)
        dst_id = self.id_gen(dpid = dst)

        lower = None
        higher = None
        if src_layer == dst_layer - 1: # src is higher
            src_port = ((dst_id.index - 1) % self.fanout) + 1
            dst_port = 0
        elif dst_layer == src_layer - 1:
            src_port = 0
            dst_port = ((src_id.index - 1) % self.fanout) + 1
        else:
            raise Exception("Could not find port leading to given dst switch")

        return (src_port, dst_port)

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