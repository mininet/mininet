#!/usr/bin/env python

"""
Test for natnet.py
"""

import unittest
import pexpect
import sys
from mininet.util import quietRun

class testNATNet( unittest.TestCase ):

    prompt = u'mininet>'

    def setUp( self ):
        self.net = pexpect.spawn( sys.executable + ' -m mininet.examples.natnet', encoding='utf-8' )
        self.net.expect( self.prompt )

    def testPublicPing( self ):
        "Attempt to ping the public server (h0) from h1 and h2"
        self.net.sendline( 'h1 ping -c 1 h0' )
        self.net.expect ( u'(\d+)% packet loss' )
        percent = int( self.net.match.group( 1 ) ) if self.net.match else -1
        self.assertEqual( percent, 0 )
        self.net.expect( self.prompt )

        self.net.sendline( 'h2 ping -c 1 h0' )
        self.net.expect ( u'(\d+)% packet loss' )
        percent = int( self.net.match.group( 1 ) ) if self.net.match else -1
        self.assertEqual( percent, 0 )
        self.net.expect( self.prompt )

    def testPrivatePing( self ):
        "Attempt to ping h1 and h2 from public server"
        self.net.sendline( 'h0 ping -c 1 -t 1 h1' )
        result = self.net.expect ( [ u'unreachable', u'loss' ] )
        self.assertEqual( result, 0 )
        self.net.expect( self.prompt )

        self.net.sendline( 'h0 ping -c 1 -t 1 h2' )
        result = self.net.expect ( [ u'unreachable', u'loss' ] )
        self.assertEqual( result, 0 )
        self.net.expect( self.prompt )

    def testPrivateToPrivatePing( self ):
        "Attempt to ping from NAT'ed host h1 to NAT'ed host h2"
        self.net.sendline( 'h1 ping -c 1 -t 1 h2' )
        result = self.net.expect ( [ u'[Uu]nreachable', u'loss' ] )
        self.assertEqual( result, 0 )
        self.net.expect( self.prompt )

    def tearDown( self ):
        self.net.sendline( 'exit' )
        self.net.wait()

if __name__ == '__main__':
    unittest.main()
