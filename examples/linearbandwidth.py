#!/usr/bin/python

"""
Test bandwidth (using iperf) on linear networks of varying size, 
using both kernel and user datapaths.

We construct a network of N switches and N+1 hosts, connected as follows:

hN <-> s0 <-> s1 .. sN-1
        |      |     |
        hN+1   hN+2  hN+N
        
Note: by default, the reference controller only supports 16
switches, so this test WILL NOT WORK unless you have recompiled
your controller to support 100 switches (or more.)
"""

import sys
flush = sys.stdout.flush
   
from mininet.net import init, Mininet
from mininet.node import Host, KernelSwitch, UserSwitch
from mininet.topo import Topo, Node
from mininet.log import lg

class LinearTopo( Topo ):
    "Topology for a string of N switches and 1+N hosts."

    def __init__( self, N ):
    
        # Add default members to class.
        super( LinearTopo, self ).__init__()
        
        # Create switch and host nodes
        switches = range( 0, N )
        hosts = range( N, 2*N + 1 )
        for id in switches:
            self._add_node( id, Node( is_switch=True ) )
        for id in hosts:
            self._add_node( id, Node( is_switch=False ) )

        # Connect switches
        for s in switches[ :-1 ]:
            self._add_edge( s, s + 1 )
            
        # Connect hosts
        self._add_edge( hosts[ 0 ], switches[ 0 ] )
        for s in switches:
            self._add_edge( s, s + N + 1)
            
        # Consider all switches and hosts 'on'
        self.enable_all()

def linearBandwidthTest( lengths ):

    "Check bandwidth at various lengths along a switch chain."

    datapaths = [ 'kernel', 'user' ]
    results = {}
    switchCount = max( lengths )

    for datapath in datapaths:
        Switch = KernelSwitch if datapath == 'kernel' else UserSwitch
        results[ datapath ] = []
        net = Mininet( topo=LinearTopo( switchCount ), switch=Switch )
        net.start()
        print "*** testing basic connectivity"
        net.ping( [ net.hosts[ 0 ], net.hosts[ -1 ] ] )
        print "*** testing bandwidth"
        for n in lengths:
            print "testing h0 <-> h" + `n`, ; flush()
            bandwidth = net.iperf( [ net.hosts[ 0 ], net.hosts[ n ] ]  )
            print bandwidth ; flush()
            results[ datapath ] += [ ( n, bandwidth ) ]
        net.stop()
      
    for datapath in datapaths:
        print
        print "*** Linear network results for", datapath, "datapath:"
        print
        result = results[ datapath ]  
        print "SwitchCount\tiperf Results"
        for switchCount, bandwidth in result:
            print switchCount, '\t\t', 
            print bandwidth[ 0 ], 'server, ', bandwidth[ 1 ], 'client'
        print
    print
      
if __name__ == '__main__':
    lg.setLogLevel( 'info' )
    init()
    print "*** Running linearBandwidthTest"
    linearBandwidthTest( [ 1, 10 ] )

   
