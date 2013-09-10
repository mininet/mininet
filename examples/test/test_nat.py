#!/usr/bin/env python

"""TEST"""

import unittest
import pexpect
#from time import sleep
from mininet.log import setLogLevel
#from mininet.net import Mininet
#from mininet.node import CPULimitedHost
#from mininet.link import TCLink

#from mininet.examples.simpleperf import SingleSwitchTopo

class testNAT( unittest.TestCase ):
    "Test ping with single switch topology (common code)."

    prompt = 'mininet>'

    # skip if 8.8.8.8 unreachable
    def testNAT( self ):
        p = pexpect.spawn( 'python -m mininet.examples.nat' )
        p.expect( self.prompt )
        p.sendline( 'h1 ping -c 1 8.8.8.8' )
        p.expect ( '(\d+)% packet loss' )
        percent = int( p.match.group( 1 ) ) if p.match else -1
        p.expect( self.prompt )
        p.sendline( 'exit' )
        p.wait()
        self.assertEqual( percent, 0 )
    '''
    def testTopo( self ):
        topo = SingleSwitchTopo(n=4)
        net = Mininet(topo=topo,
                  host=CPULimitedHost, link=TCLink)
        net.start()
        h1, h4 = net.get('h1', 'h4')
        h1.cmd( 'ping -c 1 %s' % h4.IP() )
        net.stop()
    '''

if __name__ == '__main__':
    setLogLevel( 'warning' )
    unittest.main()
