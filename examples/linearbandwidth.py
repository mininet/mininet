#!/usr/bin/env python

"""
Test bandwidth (using iperf) on linear networks of varying size,
using both kernel and user datapaths.

We construct a network of N hosts and N-1 switches, connected as follows:

h1 <-> s1 <-> s2 .. sN-1
       |       |    |
       h2      h3   hN

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

from functools import partial

from mininet.net import Mininet
from mininet.node import UserSwitch, OVSKernelSwitch, Controller
from mininet.topo import Topo
from mininet.log import lg, info
from mininet.util import irange, quietRun
from mininet.link import TCLink

flush = sys.stdout.flush


class LinearTestTopo( Topo ):
    "Topology for a string of N hosts and N-1 switches."

    # pylint: disable=arguments-differ
    def build( self, N, **params ):
        # Create switches and hosts
        hosts = [ self.addHost( 'h%s' % h )
                  for h in irange( 1, N ) ]
        switches = [ self.addSwitch( 's%s' % s )
                     for s in irange( 1, N - 1 ) ]

        # Wire up switches
        last = None
        for switch in switches:
            if last:
                self.addLink( last, switch )
            last = switch

        # Wire up hosts
        self.addLink( hosts[ 0 ], switches[ 0 ] )
        for host, switch in zip( hosts[ 1: ], switches ):
            self.addLink( host, switch )


def linearBandwidthTest( lengths ):

    "Check bandwidth at various lengths along a switch chain."

    results = {}
    switchCount = max( lengths )
    hostCount = switchCount + 1

    switches = { 'reference user': UserSwitch,
                 'Open vSwitch kernel': OVSKernelSwitch }

    # UserSwitch is horribly slow with recent kernels.
    # We can reinstate it once its performance is fixed
    del switches[ 'reference user' ]

    topo = LinearTestTopo( hostCount )

    # Select TCP Reno
    output = quietRun( 'sysctl -w net.ipv4.tcp_congestion_control=reno' )
    assert 'reno' in output

    for datapath in switches:
        info( "*** testing", datapath, "datapath\n" )
        Switch = switches[ datapath ]
        results[ datapath ] = []
        link = partial( TCLink, delay='30ms', bw=100 )
        net = Mininet( topo=topo, switch=Switch,
                       controller=Controller, link=link,
                       waitConnected=True )
        net.start()
        info( "*** testing basic connectivity\n" )
        for n in lengths:
            net.ping( [ net.hosts[ 0 ], net.hosts[ n ] ] )
        info( "*** testing bandwidth\n" )
        for n in lengths:
            src, dst = net.hosts[ 0 ], net.hosts[ n ]
            # Try to prime the pump to reduce PACKET_INs during test
            # since the reference controller is reactive
            src.cmd( 'telnet', dst.IP(), '5001' )
            info( "testing", src.name, "<->", dst.name, '\n' )
            # serverbw = received; _clientbw = buffered
            serverbw, _clientbw = net.iperf( [ src, dst ], seconds=5 )
            info( serverbw, '\n' )
            flush()
            results[ datapath ] += [ ( n, serverbw ) ]
        net.stop()

    for datapath in switches:
        info( "\n*** Linear network results for", datapath, "datapath:\n" )
        result = results[ datapath ]
        info( "SwitchCount\tiperf Results\n" )
        for switchCount, serverbw in result:
            info( switchCount, '\t\t' )
            info( serverbw, '\n' )
        info( '\n')
    info( '\n' )


if __name__ == '__main__':
    lg.setLogLevel( 'info' )
    sizes = [ 1, 2, 3, 4 ]
    info( "*** Running linearBandwidthTest", sizes, '\n' )
    linearBandwidthTest( sizes  )
