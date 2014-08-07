#!/usr/bin/env python

"""
Test for simpleperf.py
"""

import unittest
import pexpect
import re
import sys
from mininet.log import setLogLevel
from mininet.net import Mininet
from mininet.node import CPULimitedHost
from mininet.link import TCLink

from mininet.examples.simpleperf import SingleSwitchTopo

class testSimplePerf( unittest.TestCase ):

    @unittest.skipIf( '-quick' in sys.argv, 'long test' )
    def testE2E( self ):
        "Run the example and verify ping and iperf results"
        p = pexpect.spawn( 'python -m mininet.examples.simpleperf' )
        # check ping results
        p.expect( "Results: (\d+)% dropped", timeout=120 )
        loss = int( p.match.group( 1 ) )
        self.assertTrue( 0 < loss < 100 )
        # check iperf results
        p.expect( "Results: \['([\d\.]+) .bits/sec", timeout=480 )
        bw = float( p.match.group( 1 ) )
        self.assertTrue( bw > 0 )
        p.wait()

    def testTopo( self ):
        """Import SingleSwitchTopo from example and test connectivity between two hosts
           Note: this test may fail very rarely because it is non-deterministic
           i.e. links are configured with 10% packet loss, but if we get unlucky and 
           none or all of the packets are dropped, the test will fail"""
        topo = SingleSwitchTopo( n=4 )
        net = Mininet( topo=topo, host=CPULimitedHost, link=TCLink )
        net.start()
        h1, h4 = net.get( 'h1', 'h4' )
        # have h1 ping h4 ten times
        expectStr = '(\d+) packets transmitted, (\d+) received, (\d+)% packet loss'
        output = h1.cmd( 'ping -c 10 %s' % h4.IP() )
        m = re.search( expectStr, output )
        loss = int( m.group( 3 ) )
        net.stop()
        self.assertTrue( 0 < loss < 100 )

if __name__ == '__main__':
    setLogLevel( 'warning' )
    unittest.main()
