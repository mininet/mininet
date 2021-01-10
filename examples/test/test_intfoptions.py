#!/usr/bin/env python

"""
Test for intfOptions.py
"""

import unittest
from mininet.util import pexpect
import sys

class testIntfOptions( unittest.TestCase ):

    def testIntfOptions( self ):
        "verify that intf.config is correctly limiting traffic"
        p = pexpect.spawn( 'python -m mininet.examples.intfoptions ' )
        tolerance = .25  # plus or minus 25% for cloud CI tests
        opts = [ "Results: \['([\d\.]+) .bits/sec",
                 "Results: \['10M', '([\d\.]+) .bits/sec",
                 "h(\d+)->h(\d+): (\d)/(\d),"
                 "rtt min/avg/max/mdev ([\d\.]+)/([\d\.]+)/([\d\.]+)/([\d\.]+) ms",
                 pexpect.EOF ]
        while True:
            index = p.expect( opts, timeout=600 )
            if index == 0:
                BW = 10
                bw = float( p.match.group( 1 ) )
                self.assertGreaterEqual( bw, BW * ( 1 - tolerance ) )
                self.assertLessEqual( bw, BW * ( 1 + tolerance ) )
            elif index == 1:
                BW = 10
                measuredBw = float( p.match.group( 1 ) )
                loss = ( measuredBw / BW ) * 100
                self.assertGreaterEqual( loss, 50 * ( 1 - tolerance ),
                                         'loss of %d%% << 50%%' % loss )
                self.assertLessEqual( loss,  50 * ( 1 + tolerance ),
                                      'loss of %d%% >> 50%%' % loss  )
            elif index == 2:
                delay = float( p.match.group( 6 ) )
                self.assertGreaterEqual( delay, 15 * ( 1 - tolerance ) )
                self.assertLessEqual( delay,  15 * ( 1 + tolerance ) )
            else:
                break


if __name__ == '__main__':
    unittest.main()
