#!/usr/bin/env python

"""
Test for multitest.py
"""

import unittest
from mininet.util import pexpect

class testMultiTest( unittest.TestCase ):

    prompt = 'mininet>'

    def testMultiTest( self ):
        "Verify pingall (0% dropped) and hX-eth0 interface for each host (ifconfig)"
        p = pexpect.spawn( 'python -m mininet.examples.multitest' )
        p.expect( '(\d+)% dropped' )
        dropped = int( p.match.group( 1 ) )
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
    unittest.main()
