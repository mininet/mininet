#!/usr/bin/env python

"""
Test for popen.py and popenpoll.py
"""

import unittest
import pexpect

class testPopen( unittest.TestCase ):

    def pingTest( self, name ):
        "Verify that there are no dropped packets for each host"
        p = pexpect.spawn( 'python -m %s' % name )
        opts = [ "<(h\d+)>: PING ",
                 "<(h\d+)>: (\d+) packets transmitted, (\d+) received",
                 pexpect.EOF ]
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
                # verify no dropped packets
                self.assertEqual( received, transmitted )
                pings[ name ] += 1
            else:
                break
        self.assertTrue( len(pings) > 0 )
        # verify that each host has gotten results
        for count in pings.values():
            self.assertEqual( count, 1 )

    def testPopen( self ):
        self.pingTest( 'mininet.examples.popen' )

    def testPopenPoll( self ):
        self.pingTest( 'mininet.examples.popenpoll' )

if __name__ == '__main__':
    unittest.main()
