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
        p = pexpect.spawn( 'python -m mininet.examples.intfOptions ' )
        tolerance = .8
        opts = [ "Results: \['([\d\.]+) .bits/sec",
                 "(\d+) packets transmitted, (\d+) received, (\d+)% packet loss, time (\d+)ms",
                 "h(\d+)->h(\d+): (\d)/(\d), rtt min/avg/max/mdev ([\d\.]+)/([\d\.]+)/([\d\.]+)/([\d\.]+) ms",
                 pexpect.EOF ]
        while True:
            index = p.expect( opts, timeout=600 )
            if index == 0:
                bw = float( p.match.group( 1 ) )
                self.assertGreaterEqual( bw, float( 5 * tolerance ) )
                self.assertLessEqual( bw, float( 5 + 5 * ( 1 - tolerance ) ) )
            elif index == 1:
                loss = int( p.match.group( 3 ) )
                msg = ( "testing packet loss at 50%\n",
                        "this test will sometimes fail\n",
                        "ran 20 pings accross network\n",
                        "packet loss is %d%%\n\n"
                        % loss )
                self.assertGreaterEqual( loss, 50 * .8, msg )
                self.assertLessEqual( loss,  50 + 50 * ( 1 - tolerance ), msg )
            elif index == 2:
                delay = float( p.match.group( 6 ) )
                self.assertGreaterEqual( delay, 15 * .8 )
                self.assertLessEqual( delay,  15 + 15 * ( 1 - tolerance ) )
            else:
                break


if __name__ == '__main__':
    unittest.main()
