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

class testTreePing64( unittest.TestCase ):
    "Test ping with single switch topology (common code)."

    prompt = 'mininet>'

    def testTreePing64( self ):
        p = pexpect.spawn( 'python -m mininet.examples.treeping64' )
        p.expect( 'Tree network ping results:', timeout=6000 )
        count = 0
        while True:
            index = p.expect( [ '(\d+)% packet loss', pexpect.EOF ] )
            if index == 0:
                percent = int( p.match.group( 1 ) ) if p.match else -1
                self.assertEqual( percent, 0 )
                count += 1
            else:
                break
        self.assertTrue( count > 0 )

if __name__ == '__main__':
    setLogLevel( 'warning' )
    unittest.main()
