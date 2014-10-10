#!/usr/bin/env python

"""
Test for multitest.py
"""

import unittest
import pexpect

class testMultiTest( unittest.TestCase ):

    prompt = 'mininet>'

    def testMultiTest( self ):
        "Verify pingall (0% dropped) and hX-eth0 interface for each host (ifconfig)"
        p = pexpect.spawn( 'python -m mininet.examples.multitest' )
        p.expect ( '(\d+\.\d{2})% dropped' )
        percent = float( p.match.group( 1 ) ) if p.match else -1
        self.assertEqual( percent, 0 )
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
