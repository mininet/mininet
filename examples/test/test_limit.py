#!/usr/bin/env python

"""TEST"""

import unittest
import pexpect
from mininet.log import setLogLevel

class testLimit( unittest.TestCase ):
    "Test ping with single switch topology (common code)."

    def testLimit( self ):
        opts = [ '\*\*\* Testing network ([\d\.]+) Mbps', 
                 '\*\*\* Results: \[([\d\., ]+)\]', 
                 pexpect.EOF ]
        p = pexpect.spawn( 'python -m mininet.examples.limit' )
        count = 0
        bw = 0
        tolerance = 1
        while True:
            index = p.expect( opts )
            if index == 0:
                bw = float( p.match.group( 1 ) )
                count += 1
            elif index == 1:
                results = p.match.group( 1 )
                for x in results.split(','):
                    result = float( x )
                    self.assertTrue( result < bw + tolerance )
                    self.assertTrue( result > bw - tolerance)
            else:
                break

        self.assertTrue( count > 0 )

if __name__ == '__main__':
    setLogLevel( 'warning' )
    unittest.main()
