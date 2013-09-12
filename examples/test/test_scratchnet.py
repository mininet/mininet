#!/usr/bin/env python

"""
Test for scratchnet.py
"""

import unittest
import pexpect

class testScratchNet( unittest.TestCase ):

    opts = [ "1 packets transmitted, 1 received, 0% packet loss", pexpect.EOF ]

    def pingTest( self, name ):
        "Verify that no ping packets were dropped"
        p = pexpect.spawn( 'python -m %s' % name )
        index = p.expect( self.opts )
        self.assertEqual( index, 0 )

    def testPingKernel( self ):
        self.pingTest( 'mininet.examples.scratchnet' )

    def testPingUser( self ):
        self.pingTest( 'mininet.examples.scratchnetuser' )

if __name__ == '__main__':
    unittest.main()
