#!/usr/bin/env python

"""
Test for limit.py
"""

import unittest
import pexpect
import sys

class testLimit( unittest.TestCase ):

    @unittest.skipIf( '-quick' in sys.argv, 'long test' )
    def testLimit( self ):
        "Verify that CPU limits are within a 2% tolerance of limit for each scheduler"
        p = pexpect.spawn( 'python -m mininet.examples.limit' )
        opts = [ '\*\*\* Testing network ([\d\.]+) Mbps',
                 '\*\*\* Results: \[([\d\., ]+)\]',
                 pexpect.EOF ]
        count = 0
        bw = 0
        tolerance = 2
        while True:
            index = p.expect( opts )
            if index == 0:
                bw = float( p.match.group( 1 ) )
                count += 1
            elif index == 1:
                results = p.match.group( 1 )
                for x in results.split( ',' ):
                    result = float( x )
                    self.assertTrue( result < bw + tolerance )
                    self.assertTrue( result > bw - tolerance )
            else:
                break

        self.assertTrue( count > 0 )

if __name__ == '__main__':
    unittest.main()
