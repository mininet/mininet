#!/usr/bin/env python

"""
Test for linearbandwidth.py
"""

import unittest
import pexpect
import sys

class testLinearBandwidth( unittest.TestCase ):

    @unittest.skipIf( '-quick' in sys.argv, 'long test' )
    def testLinearBandwidth( self ):
        "Verify that bandwidth is monotonically decreasing as # of hops increases"
        p = pexpect.spawn( 'python -m mininet.examples.linearbandwidth' )
        count = 0
        opts = [ '\*\*\* Linear network results',
                 '(\d+)\s+([\d\.]+) (.bits)',
                 pexpect.EOF ]
        while True:
            index = p.expect( opts, timeout=600 )
            if index == 0:
                count += 1
            elif index == 1:
                n = int( p.match.group( 1 ) )
                bw = float( p.match.group( 2 ) )
                unit = p.match.group( 3 )
                if unit[ 0 ] == 'K':
                    bw *= 10 ** 3
                elif unit[ 0 ] == 'M':
                    bw *= 10 ** 6
                elif unit[ 0 ] == 'G':
                    bw *= 10 ** 9
                # check that we have a previous result to compare to
                if n != 1:
                    info = ( 'bw: %.2e bits/s across %d switches, '
                             'previous: %.2e bits/s across %d switches' %
                             ( bw, n, previous_bw, previous_n ) )
                    self.assertTrue( bw < previous_bw, info )
                previous_bw, previous_n = bw, n
            else:
                break

        # verify that we received results from at least one switch
        self.assertTrue( count > 0 )

if __name__ == '__main__':
    unittest.main()
