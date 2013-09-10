#!/usr/bin/env python

"""TEST"""

import unittest
import pexpect
from collections import defaultdict
from mininet.log import setLogLevel

class testPopen( unittest.TestCase ):
    "Test ping with single switch topology (common code)."

    def pingTest( self, name ):
        p = pexpect.spawn( 'python -m %s' % name )
        opts = []
        opts.append( "<(h\d+)>: PING " )
        opts.append( "<(h\d+)>: (\d+) packets transmitted, (\d+) received" )
        opts.append( pexpect.EOF )
        pings = {}
        while True:
            index = p.expect( opts )
            if index == 0:
                name = p.match.group(1)
                pings[ name ] = 0
            elif index == 1:
                name = p.match.group(1)
                transmitted = p.match.group(2)
                received = p.match.group(3)
                self.assertEqual( received, transmitted )
                pings[ name ] += 1
            else:
                break
        self.assertTrue( len(pings) > 0 )
        for count in pings.values():
            self.assertEqual( count, 1 )

    def testPopen( self ):
        self.pingTest( 'mininet.examples.popen' )

    def testPopenPoll( self ):
        self.pingTest( 'mininet.examples.popenpoll')

if __name__ == '__main__':
    setLogLevel( 'warning' )
    unittest.main()
