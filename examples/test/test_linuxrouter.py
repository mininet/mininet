#!/usr/bin/env python

"""
Test for linuxrouter.py
"""

import unittest
import pexpect
import sys
from mininet.util import quietRun

class testLinuxRouter( unittest.TestCase ):

    prompt = u'mininet>'

    def testPingall( self ):
        "Test connectivity between hosts"
        p = pexpect.spawn( sys.executable + ' -m mininet.examples.linuxrouter', encoding='utf-8' )
        p.expect( self.prompt )
        p.sendline( 'pingall' )
        p.expect ( u'(\d+)% dropped' )
        percent = int( p.match.group( 1 ) ) if p.match else -1
        p.expect( self.prompt )
        p.sendline( 'exit' )
        p.wait()
        self.assertEqual( percent, 0 )

    def testRouterPing( self ):
        "Test connectivity from h1 to router"
        p = pexpect.spawn( sys.executable + ' -m mininet.examples.linuxrouter', encoding='utf-8' )
        p.expect( self.prompt )
        p.sendline( 'h1 ping -c 1 r0' )
        p.expect ( u'(\d+)% packet loss' )
        percent = int( p.match.group( 1 ) ) if p.match else -1
        p.expect( self.prompt )
        p.sendline( 'exit' )
        p.wait()
        self.assertEqual( percent, 0 )

    def testTTL( self ):
        "Verify that the TTL is decremented"
        p = pexpect.spawn( sys.executable + ' -m mininet.examples.linuxrouter', encoding='utf-8' )
        p.expect( self.prompt )
        p.sendline( 'h1 ping -c 1 h2' )
        p.expect ( u'ttl=(\d+)' )
        ttl = int( p.match.group( 1 ) ) if p.match else -1
        p.expect( self.prompt )
        p.sendline( 'exit' )
        p.wait()
        self.assertEqual( ttl, 63 ) # 64 - 1

if __name__ == '__main__':
    unittest.main()
