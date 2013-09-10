#!/usr/bin/env python

"""TEST"""

import unittest
import pexpect
from time import sleep
from mininet.log import setLogLevel
from mininet.net import Mininet
from mininet.node import CPULimitedHost
from mininet.link import TCLink

from mininet.examples.simpleperf import SingleSwitchTopo

class testSimplePerf( unittest.TestCase ):
    "Test ping with single switch topology (common code)."


    def testE2E( self ):
        results = [ "Results:", pexpect.EOF, pexpect.TIMEOUT ]
        p = pexpect.spawn( 'python -m mininet.examples.simpleperf' )
        index = p.expect( results, timeout=600 )
        self.assertEqual( index, 0 )
        p.wait()

    def testTopo( self ):
        topo = SingleSwitchTopo(n=4)
        net = Mininet(topo=topo,
                  host=CPULimitedHost, link=TCLink)
        net.start()
        h1, h4 = net.get('h1', 'h4')
        h1.cmd( 'ping -c 1 %s' % h4.IP() )
        net.stop()

if __name__ == '__main__':
    setLogLevel( 'warning' )
    unittest.main()
