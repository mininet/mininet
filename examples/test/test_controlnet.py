#!/usr/bin/env python

"""
Test for controlnet.py
"""

import unittest
from mininet.util import pexpect

from sys import stdout

class testControlNet( unittest.TestCase ):

    prompt = 'mininet>'

    def testPingall( self ):
        "Simple pingall test that verifies 0% packet drop in data network"
        p = pexpect.spawn( 'python -m mininet.examples.controlnet', logfile=stdout)
        p.expect( self.prompt )
        p.sendline( 'pingall' )
        p.expect ( '(\d+)% dropped' )
        percent = int( p.match.group( 1 ) ) if p.match else -1
        self.assertEqual( percent, 0 )
        p.expect( self.prompt )
        p.sendline( 'exit' )
        p.wait()

    def testFailover( self ):
        "Kill controllers and verify that switch, s1, fails over properly"
        count = 1
        p = pexpect.spawn( 'python -m mininet.examples.controlnet', logfile=stdout )
        p.expect( self.prompt )
        lp = pexpect.spawn( 'tail -f /tmp/s1-ofp.log', logfile=stdout )
        lp.expect( 'tcp:\d+\.\d+\.\d+\.(\d+):\d+: connected' )
        ip = int( lp.match.group( 1 ) )
        self.assertEqual( count, ip )
        count += 1
        for c in [ 'c0', 'c1' ]:
            p.sendline( '%s ifconfig %s-eth0 down' % ( c, c) )
            p.expect( self.prompt )
            lp.expect( 'tcp:\d+\.\d+\.\d+\.(\d+):\d+: connected' )
            ip = int( lp.match.group( 1 ) )
            self.assertEqual( count, ip )
            count += 1
        p.sendline( 'exit' )
        p.wait()

if __name__ == '__main__':
    unittest.main()
