"Library of potentially useful topologies for Mininet"

from mininet.topo import Topo
from mininet.net import Mininet
from mininet.util import irange

class NodeID(object):
    '''Topo node identifier.'''
    dpidlist = []
    
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
                self.dpid = int(name[1:]) + max(self.dpidlist)
            else:
                self.dpid = int(name[1:])
        elif nodetype == 's':
            self.name = self.nodetype + str(dpid)
            self.dpid = dpid
            self.dpidlist.append(dpid)
        elif self.dpidlist != [] and dpid > max(self.dpidlist):
            self.nodetype = 'h'
            self.name = self.nodetype + str(dpid - max(self.dpidlist))
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
            return self.nodetype + str(self.dpid - max(self.dpidlist))
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

#    def draw(self, filename = None, edge_width = 1, node_size = 1,
#             node_color = 'g', edge_color = 'b'):
#        '''Generate image of RipL network.
#
#        @param filename filename w/ext to write; if None, show topo on screen
#        @param edge_width edge width in pixels
#        @param node_size node size in pixels
#        @param node_color node color (ex 'b' , 'green', or '#0000ff')
#        @param edge_color edge color
#        '''
#        import matplotlib.pyplot as plt
#
#        pos = {} # pos[vertex] = (x, y), where x, y in [0, 1]
#        for layer in range(len(self.node_specs)):
#            v_boxes = len(self.node_specs)
#            height = 1 - ((layer + 0.5) / v_boxes)
#
#            layer_nodes = sorted(self.layer_nodes(layer, False))
#            h_boxes = len(layer_nodes)
#            for j, dpid in enumerate(layer_nodes):
#                pos[dpid] = ((j + 0.5) / h_boxes, height)
#
#        fig = plt.figure(1)
#        fig.clf()
#        ax = fig.add_axes([0, 0, 1, 1], frameon = False)
#
#        draw_networkx_nodes(self.g, pos, ax = ax, node_size = node_size,
#                               node_color = node_color, with_labels = False)
#        # Work around networkx bug; does not handle color arrays properly
#        for edge in self.edges(False):
#            draw_networkx_edges(self.g, pos, [edge], ax = ax,
#                                edge_color = edge_color, width = edge_width)
#
#        # Work around networkx modifying axis limits
#        ax.set_xlim(0, 1.0)
#        ax.set_ylim(0, 1.0)
#        ax.set_axis_off()
#
#        if filename:
#            plt.savefig(filename)
#        else:
#            plt.show()

class TreeTopo( Topo ):
    "Topology for a tree network with a given depth and fanout."

    def __init__( self, depth=1, fanout=2 ):
        super( TreeTopo, self ).__init__()
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

<<<<<<< Updated upstream

class TorusTopo( Topo ):
    """2-D Torus topology
       WARNING: this topology has LOOPS and WILL NOT WORK
       with the default controller or any Ethernet bridge
       without STP turned on! It can be used with STP, e.g.:
       # mn --topo torus,3,3 --switch lxbr,stp=1 --test pingall"""
    def __init__( self, x, y, *args, **kwargs ):
        Topo.__init__( self, *args, **kwargs )
        if x < 3 or y < 3:
            raise Exception( 'Please use 3x3 or greater for compatibility '
                            'with 2.1' )
        hosts, switches, dpid = {}, {}, 0
        # Create and wire interior
        for i in range( 0, x ):
            for j in range( 0, y ):
                loc = '%dx%d' % ( i + 1, j + 1 )
                # dpid cannot be zero for OVS
                dpid = ( i + 1 ) * 256 + ( j + 1 )
                switch = switches[ i, j ] = self.addSwitch( 's' + loc, dpid='%016x' % dpid )
                host = hosts[ i, j ] = self.addHost( 'h' + loc )
                self.addLink( host, switch )
        # Connect switches
        for i in range( 0, x ):
            for j in range( 0, y ):
                sw1 = switches[ i, j ]
                sw2 = switches[ i, ( j + 1 ) % y ]
                sw3 = switches[ ( i + 1 ) % x, j ]
                self.addLink( sw1, sw2 )
                self.addLink( sw1, sw3 )

    

=======
class FatTreeTopo1( StructuredTopo ):

    LAYER_CORE = 0
    LAYER_AGG = 1
    LAYER_EDGE = 2
    LAYER_HOST = 3
    portlist = []
    
    def def_nopts(self, layer, name = None):
        '''Return default dict for a FatTree topo.

        @param layer layer of node
        @param name name of node
        @return d dict with layer key/val pair, plus anything else (later)
        '''
        d = {'layer': layer}
        if name:
            id = self.id_gen(name = name)
            # For hosts only, set the IP
            if layer == self.LAYER_HOST:
                d.update({'ip': id.ip_str()})
                d.update({'mac': id.mac_str()})
            d.update({'dpid': "%016x" % id.dpid})
        return d

    def __init__( self, k=4 , fanout=2, speed=1.0 ):
        core = StructuredNodeSpec(0, k, None, speed, type_str = 'core')
        agg = StructuredNodeSpec(k / 2, k / 2, speed, speed, type_str = 'agg')
        edge = StructuredNodeSpec(k / 2, k / 2, speed, speed,
                                  type_str = 'edge')
        host = StructuredNodeSpec(1, 0, speed, None, type_str = 'host')
        node_specs = [core, agg, edge, host]
        edge_specs = [StructuredEdgeSpec(speed)] * 3
        super(FatTreeTopo1, self).__init__(node_specs, edge_specs)
        self.addFatTree( k, fanout )

    def addFatTree( self, k, fanout ):
        self.id_gen = NodeID
        core_switch_count = k
        core_switches = []
        agg_switch_count = k / 2
        counter = 0
        agg_switches = []
        edg_switch_count = k / 2
        edg_switches = []
        hosts = []
        pod_count = k
        dpid = 1

        #Creates switches and hosts. cs = core switch, as = aggregation switch, es = edge switch
        for i in irange(0, core_switch_count - 1):
            core_switch_id = self.id_gen(dpid, 's').name_str()
            core_opts = self.def_nopts(self.LAYER_CORE, core_switch_id)
            switch1 = self.addSwitch(core_switch_id, **core_opts)
            core_switches.append(core_switch_id)
            #print "Added cs%s, dpid = %s" %(i, dpid)
            dpid += 1

        for j in irange(0, (k / 2)*k - 1):
            agg_switch_id = self.id_gen(dpid, 's').name_str()
            agg_opts = self.def_nopts(self.LAYER_AGG, agg_switch_id)
            switch1 = self.addSwitch(agg_switch_id, **agg_opts)
            agg_switches.append(agg_switch_id)
            #print "Added as%s, dpid = %s" %(j, dpid)
            dpid += 1
            
            edge_switch_id = self.id_gen(dpid, 's').name_str()
            edge_opts = self.def_nopts(self.LAYER_EDGE, edge_switch_id)
            switch2 = self.addSwitch(edge_switch_id, **edge_opts)
            edg_switches.append(edge_switch_id)
            #print "Added es%s, dpid = %s" %(j, dpid)
            dpid += 1

        for h in irange(0, fanout*(k / 2)*k - 1):
            host_id = self.id_gen(dpid, 'h').name_str()
            host_opts = self.def_nopts(self.LAYER_HOST, host_id)
            host1 = self.addHost(host_id, **host_opts)
            hosts.append(host_id)
            #print "Added h%s, dpid = %s" %(h, dpid)
            dpid += 1

        #Creates links between core switches and aggregation switches.
        dstport = 1
        for core_switch in irange(0, core_switch_count - 1):
            #Counter increments after every two core switches
            #This way, links don't just happen between core switch and the first aggregation switch in the pod.
            if ((core_switch % 2) == 0 and core_switch != 0):
                counter += 1
                dstport = 1
            for pod in irange(0, pod_count - 1):
                srcport = pod + 1
                src = core_switches[core_switch]
                dst = agg_switches[agg_switch_count*pod + counter]
                self.addLink(src, dst, srcport, dstport)
                #print "Link created between %s and %s. srcport=%s dstport=%s" %(self.id_gen(name = src).name_str(),
                #                                                                self.id_gen(name = dst).name_str(),
                #                                                                srcport, dstport)
                self.port(src=src, dst=dst, src_port=srcport, dst_port=dstport)
            dstport += 2

         #Creates links between aggregation switches and edge switches.
        for pod in irange(0, pod_count - 1):
            dstport = 1
            for agg_switch in irange(agg_switch_count*pod, agg_switch_count*pod + (k / 2) - 1):
                srcport = 2
                for edg_switch in irange(edg_switch_count*pod, edg_switch_count*pod + (k / 2) - 1):
                    src = agg_switches[agg_switch]
                    dst = edg_switches[edg_switch]
                    self.addLink(src, dst, srcport, dstport)
                    #print "Link created between %s and %s. srcport=%s, dstport=%s" %(self.id_gen(name = src).name_str(),
                    #                                                                 self.id_gen(name = dst).name_str(),
                    #                                                                 srcport, dstport)
                    self.port(src=src, dst=dst, src_port=srcport, dst_port=dstport)
                    srcport += 2
                dstport += 2

        # Creates links between edge switches and hosts
        for edg_switch in irange(0, (k / 2)*k - 1):
            srcport = 2
            for host in irange(0, fanout - 1):
                src = edg_switches[edg_switch]
                dst = hosts[edg_switch*fanout + host]
                self.addLink(src, dst, srcport)
                #print "Link created between %s and %s. srcport=%s, dstport=%s" %(self.id_gen(name = src).name_str(),
                #                                                                 self.id_gen(name = dst).name_str(),
                #                                                                 srcport, 0)
                self.port(src=src, dst=dst, src_port=srcport, dst_port=0)
                if srcport >= k:
                    srcport += 1
                else:
                    srcport += 2

    def port(self, src, dst, src_port=None, dst_port=None):
        '''Get port number (optional)

        Note that the topological significance of DPIDs in FatTreeTopo enables
        this function to be implemented statelessly.

        @param src source switch name
        @param dst destination switch name
        @return tuple (src_port, dst_port):
            src_port: port on source switch leading to the destination switch
            dst_port: port on destination switch leading to the source switch
        '''      

        srcid = self.id_gen(name = src).dpid
        dstid = self.id_gen(name = dst).dpid

        if ((src_port and dst_port) or dst_port == 0):
            if (len(self.portlist) <= srcid):
                self.portlist.extend([999 for i in irange(len(self.portlist), srcid)])
            if (self.portlist[srcid] == 999):
                self.portlist[srcid] = []
            if (len(self.portlist[srcid]) <= dstid):
                self.portlist[srcid].extend([999 for j in irange(len(self.portlist[srcid]), dstid)])
            self.portlist[srcid][dstid] = src_port
        
            if (len(self.portlist) <= dstid):
                self.portlist.extend([999 for i in irange(len(self.portlist), dstid)])
            if (self.portlist[dstid] == 999):
                self.portlist[dstid] = []
            if (len(self.portlist[dstid]) <= srcid):
                self.portlist[dstid].extend([999 for j in irange(len(self.portlist[dstid]), srcid)])
            self.portlist[dstid][srcid] = dst_port
        
        src_port = self.portlist[srcid][dstid]
        dst_port = self.portlist[dstid][srcid]
        #print ("for srcid %s and dstid %s srcport = %s dstport = %s" % (srcid, dstid, src_port, dst_port))

        return (src_port, dst_port)

def FatTreeNet( k=4, fanout=2, speed=1.0, **kwargs ):
    topo = FatTreeTopo1( k, fanout, speed )
    return Mininet( topo, **kwargs)
>>>>>>> Stashed changes
