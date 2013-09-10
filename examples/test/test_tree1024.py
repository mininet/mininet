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

class testTree1024( unittest.TestCase ):
    "Test ping with single switch topology (common code)."

    prompt = 'mininet>'

    def testTree1024( self ):
        p = pexpect.spawn( 'python -m mininet.examples.tree1024' )
        p.expect( self.prompt, timeout=6000 ) # it takes awhile to set up
        p.sendline( 'h1 ping -c 1 h1024' )
        p.expect ( '(\d+)% packet loss' )
        percent = int( p.match.group( 1 ) ) if p.match else -1
        #self.assertEqual( percent, 0 )
        #p.expect( self.prompt )
        #p.sendline( 'iperf' )
        #p.expect( "Results: \['\d+ .bits/sec', '\d+ .bits/sec'\]" )
        p.expect( self.prompt )
        p.sendline( 'exit' )
        p.wait()
        self.assertEqual( percent, 0 )

if __name__ == '__main__':
    setLogLevel( 'warning' )
    unittest.main()
