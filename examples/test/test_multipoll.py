#!/usr/bin/env python

"""TEST"""

import unittest
import pexpect
from collections import defaultdict
from mininet.log import setLogLevel

class testMultiPoll( unittest.TestCase ):
    "Test ping with single switch topology (common code)."

    def testMultiPoll( self ):
        p = pexpect.spawn( 'python -m mininet.examples.multipoll' )
        opts = []
        opts.append( "\*\*\* (h\d) :" )
        opts.append( "(h\d+): \d+ bytes from" )
        opts.append( "Monitoring output for (\d+) seconds" )
        opts.append( pexpect.EOF )
        pings = {}
        while True:
            index = p.expect( opts )
            if index == 0:
                name = p.match.group( 1 )
                pings[ name ] = 0
            elif index == 1:
                name = p.match.group( 1 )
                pings[ name ] += 1
            elif index == 2:
                seconds = int( p.match.group( 1 ) )
            else:
                break
        self.assertTrue( len(pings) > 0 )
        # make sure we have received at least one ping per second
        for count in pings.values():
            self.assertTrue( count >= seconds )

if __name__ == '__main__':
    setLogLevel( 'warning' )
    unittest.main()
