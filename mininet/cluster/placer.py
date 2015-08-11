#!/usr/bin/python
# Some simple placement algorithms for MininetCluster

from mininet.util import quietRun, errRun
from mininet.log import setLogLevel, debug, info, error

import os
from random import randrange


class Placer( object ):
    "Node placement algorithm for MininetCluster"

    def __init__( self, servers=None, nodes=None, hosts=None,
                  switches=None, controllers=None, links=None ):
        """Initialize placement object
           servers: list of servers
           nodes: list of all nodes
           hosts: list of hosts
           switches: list of switches
           controllers: list of controllers
           links: list of links
           (all arguments are optional)
           returns: server"""
        self.servers = servers or []
        self.nodes = nodes or []
        self.hosts = hosts or []
        self.switches = switches or []
        self.controllers = controllers or []
        self.links = links or []

    def place( self, node ):
        "Return server for a given node"
        assert self, node  # satisfy pylint
        # Default placement: run locally
        return 'localhost'


class RandomPlacer( Placer ):
    "Random placement"
    def place( self, nodename ):
        """Random placement function
            nodename: node name"""
        assert nodename  # please pylint
        # This may be slow with lots of servers
        return self.servers[ randrange( 0, len( self.servers ) ) ]


class RoundRobinPlacer( Placer ):
    """Round-robin placement
       Note this will usually result in cross-server links between
       hosts and switches"""

    def __init__( self, *args, **kwargs ):
        Placer.__init__( self, *args, **kwargs )
        self.next = 0

    def place( self, nodename ):
        """Round-robin placement function
            nodename: node name"""
        assert nodename  # please pylint
        # This may be slow with lots of servers
        server = self.servers[ self.next ]
        self.next = ( self.next + 1 ) % len( self.servers )
        return server


class SwitchBinPlacer( Placer ):
    """Place switches (and controllers) into evenly-sized bins,
       and attempt to co-locate hosts and switches"""

    def __init__( self, *args, **kwargs ):
        Placer.__init__( self, *args, **kwargs )
        # Easy lookup for servers and node sets
        self.servdict = dict( enumerate( self.servers ) )
        self.hset = frozenset( self.hosts )
        self.sset = frozenset( self.switches )
        self.cset = frozenset( self.controllers )
        # Server and switch placement indices
        self.placement = self.calculatePlacement()

    @staticmethod
    def bin( nodes, servers ):
        "Distribute nodes evenly over servers"
        # Calculate base bin size
        nlen = len( nodes )
        slen = len( servers )
        # Basic bin size
        quotient = int( nlen / slen )
        binsizes = { server: quotient for server in servers }
        # Distribute remainder
        remainder = nlen % slen
        for server in servers[ 0 : remainder ]:
            binsizes[ server ] += 1
        # Create binsize[ server ] tickets for each server
        tickets = sum( [ binsizes[ server ] * [ server ]
                         for server in servers ], [] )
        # And assign one ticket to each node
        return { node: ticket for node, ticket in zip( nodes, tickets ) }

    def calculatePlacement( self ):
        "Pre-calculate node placement"
        placement = {}
        # Create host-switch connectivity map,
        # associating host with last switch that it's
        # connected to
        switchFor = {}
        for src, dst in self.links:
            if src in self.hset and dst in self.sset:
                switchFor[ src ] = dst
            if dst in self.hset and src in self.sset:
                switchFor[ dst ] = src
        # Place switches
        placement = self.bin( self.switches, self.servers )
        # Place controllers and merge into placement dict
        placement.update( self.bin( self.controllers, self.servers ) )
        # Co-locate hosts with their switches
        for h in self.hosts:
            if h in placement:
                # Host is already placed - leave it there
                continue
            if h in switchFor:
                placement[ h ] = placement[ switchFor[ h ] ]
            else:
                raise Exception(
                        "SwitchBinPlacer: cannot place isolated host " + h )
        return placement

    def place( self, node ):
        """Simple placement algorithm:
           place switches into evenly sized bins,
           and place hosts near their switches"""
        return self.placement[ node ]


class HostSwitchBinPlacer( Placer ):
    """Place switches *and hosts* into evenly-sized bins
       Note that this will usually result in cross-server
       links between hosts and switches"""

    def __init__( self, *args, **kwargs ):
        Placer.__init__( self, *args, **kwargs )
        # Calculate bin sizes
        scount = len( self.servers )
        self.hbin = max( int( len( self.hosts ) / scount ), 1 )
        self.sbin = max( int( len( self.switches ) / scount ), 1 )
        self.cbin = max( int( len( self.controllers ) / scount ), 1 )
        info( 'scount:', scount )
        info( 'bins:', self.hbin, self.sbin, self.cbin, '\n' )
        self.servdict = dict( enumerate( self.servers ) )
        self.hset = frozenset( self.hosts )
        self.sset = frozenset( self.switches )
        self.cset = frozenset( self.controllers )
        self.hind, self.sind, self.cind = 0, 0, 0

    def place( self, nodename ):
        """Simple placement algorithm:
            place nodes into evenly sized bins"""
        # Place nodes into bins
        if nodename in self.hset:
            server = self.servdict[ self.hind / self.hbin ]
            self.hind += 1
        elif nodename in self.sset:
            server = self.servdict[ self.sind / self.sbin ]
            self.sind += 1
        elif nodename in self.cset:
            server = self.servdict[ self.cind / self.cbin ]
            self.cind += 1
        else:
            info( 'warning: unknown node', nodename )
            server = self.servdict[ 0 ]
        return server
