"Library of potentially useful topologies for Mininet"

from mininet.topo import  Topo, NodeID
from mininet.log import debug
from ripl.dctopo import StructuredEdgeSpec, StructuredNodeSpec, StructuredTopo
from mininet.net import Mininet
from mininet.util import irange

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

    

class FatTreeTopo1( StructuredTopo ):
    '''Topology with a fat tree with given k and fanout for hosts.
       Topology consists of k core switches, 2*k aggregation and edge 
       switches, and fanout*(k / 2)*k hosts. This topology WILL NOT WORK
       with the default controller. It can be used with a data center
       multi-path enabled controller such as RiplPOX'''

    LAYER_CORE = 0
    LAYER_AGG = 1
    LAYER_EDGE = 2
    LAYER_HOST = 3
    portlist = [] 
    
    def def_nopts( self, layer, name=None ):
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
        core = StructuredNodeSpec( 0, k, None, speed, type_str = 'core' )
        agg = StructuredNodeSpec( k / 2, k / 2, speed, speed, type_str = 'agg' )
        edge = StructuredNodeSpec( k / 2, k / 2, speed, speed,
                                  type_str = 'edge' )
        host = StructuredNodeSpec( 1, 0, speed, None, type_str = 'host' )
        node_specs = [ core, agg, edge, host ]
        edge_specs = [ StructuredEdgeSpec(speed) ] * 3
        super( FatTreeTopo1, self ).__init__( node_specs, edge_specs )
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
        for i in irange( 0, core_switch_count - 1 ):
            core_switch_id = self.id_gen( dpid, 's' ).name_str()
            core_opts = self.def_nopts( self.LAYER_CORE, core_switch_id )
            switch1 = self.addSwitch( core_switch_id, **core_opts )
            core_switches.append( core_switch_id )
            debug( "Added cs%s, dpid = %s" %( i, dpid ) + "\n" )
            dpid += 1

        for j in irange( 0, (k / 2)*k - 1 ):
            agg_switch_id = self.id_gen( dpid, 's' ).name_str()
            agg_opts = self.def_nopts( self.LAYER_AGG, agg_switch_id )
            switch1 = self.addSwitch( agg_switch_id, **agg_opts )
            agg_switches.append( agg_switch_id )
            debug( "Added as%s, dpid = %s" %( j, dpid ) + "\n" )
            dpid += 1
            
            edge_switch_id = self.id_gen( dpid, 's' ).name_str()
            edge_opts = self.def_nopts( self.LAYER_EDGE, edge_switch_id )
            switch2 = self.addSwitch( edge_switch_id, **edge_opts )
            edg_switches.append( edge_switch_id )
            debug( "Added es%s, dpid = %s" %( j, dpid ) + "\n" )
            dpid += 1

        for h in irange( 0, fanout*(k / 2)*k - 1 ):
            host_id = self.id_gen( dpid, 'h' ).name_str()
            host_opts = self.def_nopts( self.LAYER_HOST, host_id )
            host1 = self.addHost( host_id, **host_opts )
            hosts.append( host_id )
            debug( "Added h%s, dpid = %s" %( h, dpid ) + "\n" )
            dpid += 1

        #Creates links between core switches and aggregation switches.
        dstport = 1
        for core_switch in irange( 0, core_switch_count - 1 ):
            #Counter increments after every two core switches
            #This way, links don't just happen between core switch and the first aggregation switch in the pod.
            if (( core_switch % 2 ) == 0 and core_switch != 0 ):
                counter += 1
                dstport = 1
            for pod in irange( 0, pod_count - 1 ):
                srcport = pod + 1
                src = core_switches[ core_switch ]
                dst = agg_switches[ agg_switch_count*pod + counter ]
                self.addLink( src, dst, srcport, dstport )
                debug( "Link created between %s and %s. srcport=%s dstport=%s" %( self.id_gen( name = src ).name_str(),
                                                                                self.id_gen( name = dst ).name_str(),
                                                                                srcport, dstport ) + "\n" )
                self.port( src=src, dst=dst, src_port=srcport, dst_port=dstport )
            dstport += 2

        #Creates links between aggregation switches and edge switches.
        for pod in irange( 0, pod_count - 1 ):
            dstport = 1
            for agg_switch in irange( agg_switch_count*pod, agg_switch_count*pod + ( k / 2 ) - 1 ):
                srcport = 2
                for edg_switch in irange( edg_switch_count*pod, edg_switch_count*pod + ( k / 2 ) - 1 ):
                    src = agg_switches[ agg_switch ]
                    dst = edg_switches[ edg_switch ]
                    self.addLink( src, dst, srcport, dstport )
                    debug( "Link created between %s and %s. srcport=%s, dstport=%s" %( self.id_gen( name = src ).name_str(),
                                                                                     self.id_gen( name = dst ).name_str(),
                                                                                     srcport, dstport ) + "\n" )
                    self.port( src=src, dst=dst, src_port=srcport, dst_port=dstport )
                    srcport += 2
                dstport += 2

        # Creates links between edge switches and hosts
        for edg_switch in irange( 0, ( k / 2 )*k - 1 ):
            srcport = 2
            for host in irange( 0, fanout - 1 ):
                src = edg_switches[ edg_switch ]
                dst = hosts[ edg_switch*fanout + host ]
                self.addLink( src, dst, srcport )
                debug( "Link created between %s and %s. srcport=%s, dstport=%s" %( self.id_gen( name = src ).name_str(),
                                                                                 self.id_gen( name = dst ).name_str(),
                                                                                 srcport, 0 ) + "\n" )
                self.port( src=src, dst=dst, src_port=srcport, dst_port=0 )
                if srcport >= k:
                    srcport += 1
                else:
                    srcport += 2

    def port( self, src, dst, src_port=None, dst_port=None ):
        '''Get port number.

        Portlist stores list of all available ports. portlist[srcid][dstid] 
        will be the source port number from switch srcid going to switch
        dstid. All other values in the list are given empty values of None. 
        
        Ex. portlist = [None, None, None, [None, 2]]
            portlist[3][1] = 2 which means source port number is 2 for the link
            from switch 3 to switch 1

        @param src source switch name
        @param dst destination switch name
        @param src_port source port added to portlist when link created
        @param dst_port destination port added to portlist when link created
        @return tuple (src_port, dst_port):
            src_port: port on source switch leading to the destination switch
            dst_port: port on destination switch leading to the source switch
        '''      

        srcid = self.id_gen( name = src ).dpid
        dstid = self.id_gen( name = dst ).dpid

        if (( src_port and dst_port ) or dst_port == 0 ):
            if len(self.portlist) <= srcid:
                self.portlist.extend( [None for i in irange(len(self.portlist), srcid)] )
            if self.portlist[srcid] == None:
                self.portlist[srcid] = []
            if len(self.portlist[srcid]) <= dstid:
                self.portlist[srcid].extend( [None for j in irange(len(self.portlist[srcid]), dstid)] )
            self.portlist[srcid][dstid] = src_port
        
            if len(self.portlist) <= dstid:
                self.portlist.extend( [None for i in irange(len(self.portlist), dstid)] )
            if self.portlist[dstid] == None:
                self.portlist[dstid] = []
            if len(self.portlist[dstid]) <= srcid:
                self.portlist[dstid].extend( [None for j in irange(len(self.portlist[dstid]), srcid)] )
            self.portlist[dstid][srcid] = dst_port
        
        src_port = self.portlist[srcid][dstid]
        dst_port = self.portlist[dstid][srcid]
        debug( "for srcid %s and dstid %s srcport = %s dstport = %s" % ( srcid, dstid, src_port, dst_port ) + "\n" )

        return ( src_port, dst_port )

def FatTreeNet( k=4, fanout=2, speed=1.0, **kwargs ):
    topo = FatTreeTopo1( k, fanout, speed )
    return Mininet( topo, **kwargs)
