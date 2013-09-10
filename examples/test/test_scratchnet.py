#!/usr/bin/env python

"""TEST"""

import unittest
import pexpect
from mininet.log import setLogLevel

class testScratchNet( unittest.TestCase ):
    "Test ping with single switch topology (common code)."

    results = [ "1 packets transmitted, 1 received, 0% packet loss", pexpect.EOF ]

    def pingTest( self, name ):
        p = pexpect.spawn( 'python -m %s' % name )
        index = p.expect( self.results )
        self.assertEqual( index, 0 )


    def testPingKernel( self ):
        self.pingTest( 'mininet.examples.scratchnet' )


    def testPingUser( self ):
        self.pingTest( 'mininet.examples.scratchnetuser' )

if __name__ == '__main__':
    setLogLevel( 'warning' )
    unittest.main()
