#!/usr/bin/env python

"""
Test for treeping64.py
"""

import unittest
from mininet.util import pexpect
import sys

class testTreePing64( unittest.TestCase ):

    prompt = 'mininet>'

    @unittest.skipIf( '-quick' in sys.argv, 'long test' )
    def testTreePing64( self ):
        "Run the example and verify ping results"
        p = pexpect.spawn( 'python -m mininet.examples.treeping64' )
        p.expect( 'Tree network ping results:', timeout=6000 )
        count = 0
        while True:
            index = p.expect( [ '(\d+)% packet loss', pexpect.EOF ] )
            if index == 0:
                percent = int( p.match.group( 1 ) ) if p.match else -1
                self.assertEqual( percent, 0 )
                count += 1
            else:
                break
        self.assertTrue( count > 0 )

if __name__ == '__main__':
    unittest.main()
