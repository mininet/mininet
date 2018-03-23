#!/usr/bin/env python

"""
Test for nat.py
"""

import unittest
import pexpect
import sys
from mininet.util import quietRun

destIP = '8.8.8.8' # Google DNS

class testNAT( unittest.TestCase ):

    prompt = u'mininet>'

    @unittest.skipIf( u'0 received' in quietRun( 'ping -c 1 %s' % destIP ),
                      u'Destination IP is not reachable' )
    def testNAT( self ):
        "Attempt to ping an IP on the Internet and verify 0% packet loss"
        p = pexpect.spawn( sys.executable + ' -m mininet.examples.nat', encoding='utf-8' )
        p.expect( self.prompt )
        p.sendline( 'h1 ping -c 10 %s' % destIP )
        p.expect ( u'(\d+)% packet loss' )
        percent = int( p.match.group( 1 ) ) if p.match else 100
        p.expect( self.prompt )
        p.sendline( 'exit' )
        p.wait()
        self.assertLess( percent, 80 )

if __name__ == '__main__':
    unittest.main()
