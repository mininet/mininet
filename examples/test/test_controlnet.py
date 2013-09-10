#!/usr/bin/env python

"""TEST"""

import unittest
import pexpect
from mininet.log import setLogLevel
#from mininet.net import Mininet
#from mininet.node import CPULimitedHost
#from mininet.link import TCLink

#from mininet.examples.simpleperf import SingleSwitchTopo

class testControlNet( unittest.TestCase ):
    "Test ping with single switch topology (common code)."

    prompt = 'mininet>'

    def testPingall( self ):
        p = pexpect.spawn( 'python -m mininet.examples.controlnet' )
        p.expect( self.prompt )
        p.sendline( 'pingall' )
        p.expect ( '(\d+)% dropped' )
        percent = int( p.match.group( 1 ) ) if p.match else -1
        self.assertEqual( percent, 0 )
        p.expect( self.prompt )
        p.sendline( 'exit' )
        p.wait()

    def testFailover( self ):
        count = 1
        p = pexpect.spawn( 'python -m mininet.examples.controlnet' )
        p.expect( self.prompt )
        lp = pexpect.spawn( 'tail -f /tmp/s1-ofp.log' )
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
    setLogLevel( 'warning' )
    unittest.main()
