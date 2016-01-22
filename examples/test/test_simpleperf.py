#!/usr/bin/env python

"""
Test for simpleperf.py
"""

import unittest
import pexpect
import sys
from mininet.log import setLogLevel

from mininet.examples.simpleperf import SingleSwitchTopo

class testSimplePerf( unittest.TestCase ):

    @unittest.skipIf( '-quick' in sys.argv, 'long test' )
    def testE2E( self ):
        "Run the example and verify iperf results"
        # 10 Mb/s, plus or minus 20% tolerance
        BW = 10
	TOLERANCE = .2 
        p = pexpect.spawn( 'python -m mininet.examples.simpleperf testmode' )
        # check iperf results
        p.expect( "Results: \['10M', '([\d\.]+) .bits/sec", timeout=480 )
        measuredBw = float( p.match.group( 1 ) )
        lowerBound = BW * ( 1 - TOLERANCE )
        upperBound = BW + ( 1 + TOLERANCE )
        self.assertGreaterEqual( measuredBw, lowerBound )
        self.assertLessEqual( measuredBw, upperBound )
        p.wait()

if __name__ == '__main__':
    setLogLevel( 'warning' )
    unittest.main()
