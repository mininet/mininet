#!/usr/bin/python

"""
Test bandwidth (using iperf) on linear networks of varying size, 
using both kernel and user datapaths.

We construct a network of N hosts and N-1 switches, connected as follows:

h1 <-> sN+1 <-> sN+2 .. sN+N-1
       |        |       |
       h2       h3      hN
        
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
    "Topology for a string of N hosts and N-1 switches."

    def __init__( self, N ):
    
        # Add default members to class.
        super( LinearTopo, self ).__init__()
        
        # Create switch and host nodes
        hosts = range( 1, N+1 )
        switches = range( N+1, N+N )
        for id in hosts:
            self._add_node( id, Node( is_switch=False ) )
        for id in switches:
            self._add_node( id, Node( is_switch=True ) )
        
        # Wire up switches
        for s in switches[ :-1 ]:
            self._add_edge( s, s + 1 )
        
        # Wire up hosts
        self._add_edge( hosts[ 0 ], switches[ 0 ] )
        for h in hosts[ 1: ]:
            self._add_edge( h, h+N-1 )

        # Consider all switches and hosts 'on'
        self.enable_all()

def linearBandwidthTest( lengths ):

    "Check bandwidth at various lengths along a switch chain."

    datapaths = [ 'kernel', 'user' ]
    results = {}
    switchCount = max( lengths )
    hostCount = switchCount + 1

    for datapath in datapaths:
        Switch = KernelSwitch if datapath == 'kernel' else UserSwitch
        results[ datapath ] = []
        net = Mininet( topo=LinearTopo( hostCount ), switch=Switch )
        net.start()
        print "*** testing basic connectivity"
        net.ping( [ net.hosts[ 0 ], net.hosts[ -1 ] ] )
        print "*** testing bandwidth"
        for n in lengths:
            src, dst = net.hosts[ 0 ], net.hosts[ n ]
            print "testing", src.name, "<->", dst.name
            bandwidth = net.iperf( [ src, dst ] )
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
    linearBandwidthTest( [ 1, 10, 20  ]  )

   
