#!/usr/bin/env python

"""TEST"""

import unittest
import pexpect
from mininet.log import setLogLevel

class testMultiTest( unittest.TestCase ):
    "Test ping with single switch topology (common code)."

    prompt = 'mininet>'

    def testMultiTest( self ):
        p = pexpect.spawn( 'python -m mininet.examples.multitest' )
        p.expect( '(\d+)% dropped' )
        dropped = int( p.match.group(1) )
        self.assertEqual( dropped, 0 )
        ifCount = 0
        while True:
            index = p.expect( [ 'h\d-eth0', self.prompt ] )
            if index == 0:
                ifCount += 1
            elif index == 1:
                p.sendline( 'exit' )
                break
        p.wait()
        self.assertEqual( ifCount, 4 )

if __name__ == '__main__':
    setLogLevel( 'warning' )
    unittest.main()
