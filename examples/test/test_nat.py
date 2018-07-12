#!/usr/bin/env python

"""
Test for nat.py
"""

import unittest
from mininet.util import pexpect
from mininet.util import quietRun

destIP = '8.8.8.8' # Google DNS

class testNAT( unittest.TestCase ):

    prompt = 'mininet>'

    @unittest.skipIf( '0 received' in quietRun( 'ping -c 1 %s' % destIP ),
                      'Destination IP is not reachable' )
    def testNAT( self ):
        "Attempt to ping an IP on the Internet and verify 0% packet loss"
        p = pexpect.spawn( 'python -m mininet.examples.nat' )
        p.expect( self.prompt )
        p.sendline( 'h1 ping -c 1 %s' % destIP )
        p.expect ( '(\d+)% packet loss' )
        percent = int( p.match.group( 1 ) ) if p.match else -1
        p.expect( self.prompt )
        p.sendline( 'exit' )
        p.wait()
        self.assertEqual( percent, 0 )

if __name__ == '__main__':
    unittest.main()
