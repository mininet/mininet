#!/usr/bin/env python

"""
Test for multipoll.py
"""

import unittest
import pexpect

class testMultiPoll( unittest.TestCase ):

    def testMultiPoll( self ):
        "Verify that we receive one ping per second per host"
        p = pexpect.spawn( 'python -m mininet.examples.multipoll' )
        opts = [ "\*\*\* (h\d) :" ,
                 "(h\d+): \d+ bytes from",
                 "Monitoring output for (\d+) seconds",
                 pexpect.EOF ]
        pings, seconds = {}, -1
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
        self.assertTrue( len( pings ) > 0 )
        # make sure we have received at least one ping per second
        for count in pings.values():
            self.assertTrue( count >= seconds,
                             '%d pings < %d seconds' % ( count, seconds ) )

if __name__ == '__main__':
    unittest.main()
