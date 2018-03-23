#!/usr/bin/env python

"""
Test for controlnet.py
"""

import unittest
import pexpect
import sys

class testControlNet( unittest.TestCase ):

    prompt = u'mininet>'

    def testPingall( self ):
        "Simple pingall test that verifies 0% packet drop in data network"
        p = pexpect.spawn( sys.executable + ' -m mininet.examples.controlnet', encoding='utf-8' )
        p.expect( self.prompt )
        p.sendline( 'pingall' )
        p.expect ( u'(\d+)% dropped' )
        percent = int( p.match.group( 1 ) ) if p.match else -1
        self.assertEqual( percent, 0 )
        p.expect( self.prompt )
        p.sendline( 'exit' )
        p.wait()

    def testFailover( self ):
        "Kill controllers and verify that switch, s1, fails over properly"
        count = 1
        p = pexpect.spawn( sys.executable + ' -m mininet.examples.controlnet', encoding='utf-8' )
        p.expect( self.prompt )
        lp = pexpect.spawn( 'tail -f /tmp/s1-ofp.log', encoding='utf-8' )
        lp.expect( u'tcp:\d+\.\d+\.\d+\.(\d+):\d+: connected' )
        ip = int( lp.match.group( 1 ) )
        self.assertEqual( count, ip )
        count += 1
        for c in [ 'c0', 'c1' ]:
            p.sendline( '%s ifconfig %s-eth0 down' % ( c, c) )
            p.expect( self.prompt )
            lp.expect( u'tcp:\d+\.\d+\.\d+\.(\d+):\d+: connected' )
            ip = int( lp.match.group( 1 ) )
            self.assertEqual( count, ip )
            count += 1
        p.sendline( 'exit' )
        p.wait()

if __name__ == '__main__':
    unittest.main()
