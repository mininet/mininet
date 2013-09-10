#!/usr/bin/env python

"""TEST"""

import unittest
import pexpect
from mininet.log import setLogLevel
#from mininet.net import Mininet
#from mininet.node import CPULimitedHost
#from mininet.link import TCLink

#from mininet.examples.simpleperf import SingleSwitchTopo

class testLinearBandwidth( unittest.TestCase ):
    "Test ping with single switch topology (common code)."

    prompt = 'mininet>'

    def testLinearBandwidth( self ):
        count = 0
        tolerance = 0.5
        opts = [ '\*\*\* Linear network results', '(\d+)\s+([\d\.]+) (.bits)', pexpect.EOF ]
        p = pexpect.spawn( 'python -m mininet.examples.linearbandwidth' )
        while True:
            index = p.expect( opts, timeout=600 )
            if index == 0:
                previous_bw = 10 ** 10 # 10 Gbits
                count += 1
            elif index == 1:
                n = int( p.match.group( 1 ) )
                bw = float( p.match.group( 2 ) )
                unit = p.match.group( 3 )
                if unit[ 0 ] == 'K':
                    bw *= 10 ** 3
                elif unit[ 0 ] == 'M':
                    bw *= 10 ** 6
                elif unit[ 0 ] == 'G':
                    bw *= 10 ** 9
                self.assertTrue( bw < previous_bw )
                previous_bw = bw
            else:
                break

        self.assertTrue( count > 0 )

if __name__ == '__main__':
    setLogLevel( 'warning' )
    unittest.main()
