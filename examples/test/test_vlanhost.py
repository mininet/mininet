#!/usr/bin/env python

"""
Test for vlanhost.py
"""

import unittest
from mininet.util import pexpect
import sys
from mininet.util import quietRun

class testVLANHost( unittest.TestCase ):

    prompt = 'mininet>'

    @unittest.skipIf( '-quick' in sys.argv, 'long test' )
    def testVLANTopo( self ):
        "Test connectivity (or lack thereof) between hosts in VLANTopo"
        p = pexpect.spawn( 'python -m mininet.examples.vlanhost' )
        p.expect( self.prompt )
        p.sendline( 'pingall 1' ) #ping timeout=1
        p.expect( '(\d+)% dropped', timeout=30  ) # there should be 24 failed pings
        percent = int( p.match.group( 1 ) ) if p.match else -1
        p.expect( self.prompt )
        p.sendline( 'exit' )
        p.wait()
        self.assertEqual( percent, 80 )

    def testSpecificVLAN( self ):
        "Test connectivity between hosts on a specific VLAN"
        vlan = 1001
        p = pexpect.spawn( 'python -m mininet.examples.vlanhost %d' % vlan )
        p.expect( self.prompt )

        p.sendline( 'h1 ping -c 1 h2' )
        p.expect ( '(\d+)% packet loss' )
        percent = int( p.match.group( 1 ) ) if p.match else -1
        p.expect( self.prompt )

        p.sendline( 'h1 ifconfig' )
        i = p.expect( ['h1-eth0.%d' % vlan, pexpect.TIMEOUT ], timeout=2 )
        p.expect( self.prompt )

        p.sendline( 'exit' )
        p.wait()
        self.assertEqual( percent, 0 ) # no packet loss on ping
        self.assertEqual( i, 0 ) # check vlan intf is present

if __name__ == '__main__':
    unittest.main()
