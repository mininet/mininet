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
                previous_bw = 10 ** 10 # 10 Gbits
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
                self.assertTrue( bw < previous_bw )
                previous_bw = bw
            else:
                break

        self.assertTrue( count > 0 )

if __name__ == '__main__':
    unittest.main()
