#!/usr/bin/env python

"""
Test for intfOptions.py
"""

import unittest
import pexpect
import sys

class testIntfOptions( unittest.TestCase ):

    def testIntfOptions( self ):
        "verify that intf.config is correctly limiting traffic"
        p = pexpect.spawn( sys.executable + ' -m mininet.examples.intfoptions ', encoding='utf-8' )
        tolerance = .2  # plus or minus 20%
        opts = [ u"Results: \['([\d\.]+) .bits/sec",
                 u"Results: \['10M', '([\d\.]+) .bits/sec",
                 u"h(\d+)->h(\d+): (\d)/(\d),"
                 u"rtt min/avg/max/mdev ([\d\.]+)/([\d\.]+)/([\d\.]+)/([\d\.]+) ms",
                 pexpect.EOF ]
        while True:
            index = p.expect( opts, timeout=600 )
            if index == 0:
                BW = 5
                bw = float( p.match.group( 1 ) )
                self.assertGreaterEqual( bw, BW * ( 1 - tolerance ) )
                self.assertLessEqual( bw, BW * ( 1 + tolerance ) )
            elif index == 1:
                BW = 10
                measuredBw = float( p.match.group( 1 ) )
                loss = ( measuredBw / BW ) * 100
                self.assertGreaterEqual( loss, 50 * ( 1 - tolerance ) )
                self.assertLessEqual( loss,  50 * ( 1 + tolerance ) )
            elif index == 2:
                delay = float( p.match.group( 6 ) )
                self.assertGreaterEqual( delay, 15 * ( 1 - tolerance ) )
                self.assertLessEqual( delay,  15 * ( 1 + tolerance ) )
            else:
                break


if __name__ == '__main__':
    unittest.main()
