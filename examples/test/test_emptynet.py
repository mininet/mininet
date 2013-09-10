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

class testEmptyNet( unittest.TestCase ):
    "Test ping with single switch topology (common code)."

    prompt = 'mininet>'

    def testEmptyNet( self ):
        p = pexpect.spawn( 'python -m mininet.examples.emptynet' )
        p.expect( self.prompt )
        p.sendline( 'pingall' )
        p.expect ( '(\d+)% dropped' )
        percent = int( p.match.group( 1 ) ) if p.match else -1
        self.assertEqual( percent, 0 ) # or this
        p.expect( self.prompt )
        p.sendline( 'iperf' )
        p.expect( "Results: \['[\d.]+ .bits/sec', '[\d.]+ .bits/sec'\]" )
        #TODO check the results? maybe we dont care
        p.expect( self.prompt )
        p.sendline( 'exit' )
        p.wait()
        #TODO remove this
        self.assertEqual( percent, 0 )

if __name__ == '__main__':
    setLogLevel( 'warning' )
    unittest.main()
