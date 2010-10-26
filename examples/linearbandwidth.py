#!/usr/bin/python

"""
Test bandwidth (using iperf) on linear networks of varying size,
using both kernel and user datapaths.

We construct a network of N hosts and N-1 switches, connected as follows:

h1 <-> sN+1 <-> sN+2 .. sN+N-1
       |        |       |
       h2       h3      hN

WARNING: by default, the reference controller only supports 16
switches, so this test WILL NOT WORK unless you have recompiled
your controller to support 100 switches (or more.)

In addition to testing the bandwidth across varying numbers
of switches, this example demonstrates:

- creating a custom topology, LinearTestTopo
- using the ping() and iperf() tests from Mininet()
- testing both the kernel and user switches

"""

import sys
flush = sys.stdout.flush

from mininet.net import init, Mininet
# from mininet.node import KernelSwitch
from mininet.node import UserSwitch, OVSKernelSwitch
from mininet.topo import Topo, Node
from mininet.log import lg

class LinearTestTopo( Topo ):
    "Topology for a string of N hosts and N-1 switches."

    def __init__( self, N ):

        # Add default members to class.
        super( LinearTestTopo, self ).__init__()

        # Create switch and host nodes
        hosts = range( 1, N + 1 )
        switches = range( N + 1 , N + N )
        for h in hosts:
            self.add_node( h, Node( is_switch=False ) )
        for s in switches:
            self.add_node( s, Node( is_switch=True ) )

        # Wire up switches
        for s in switches[ :-1 ]:
            self.add_edge( s, s + 1 )

        # Wire up hosts
        self.add_edge( hosts[ 0 ], switches[ 0 ] )
        for h in hosts[ 1: ]:
            self.add_edge( h, h + N - 1 )

        # Consider all switches and hosts 'on'
        self.enable_all()


def linearBandwidthTest( lengths ):

    "Check bandwidth at various lengths along a switch chain."

    results = {}
    switchCount = max( lengths )
    hostCount = switchCount + 1

    switches = {  # 'reference kernel': KernelSwitch,
            'reference user': UserSwitch,
            'Open vSwitch kernel': OVSKernelSwitch }

    for datapath in switches.keys():
        print "*** testing", datapath, "datapath"
        Switch = switches[ datapath ]
        results[ datapath ] = []
        net = Mininet( topo=LinearTestTopo( hostCount ), switch=Switch )
        net.start()
        print "*** testing basic connectivity"
        for n in lengths:
            net.ping( [ net.hosts[ 0 ], net.hosts[ n ] ] )
        print "*** testing bandwidth"
        for n in lengths:
            src, dst = net.hosts[ 0 ], net.hosts[ n ]
            print "testing", src.name, "<->", dst.name,
            bandwidth = net.iperf( [ src, dst ] )
            print bandwidth
            flush()
            results[ datapath ] += [ ( n, bandwidth ) ]
        net.stop()

    for datapath in switches.keys():
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
    sizes = [ 1, 10, 20, 40, 60, 80, 100 ]
    print "*** Running linearBandwidthTest", sizes
    linearBandwidthTest( sizes  )
