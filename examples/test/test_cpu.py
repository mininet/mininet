#!/usr/bin/env python

"""TEST"""

import unittest
import pexpect
from mininet.log import setLogLevel

class testCPU( unittest.TestCase ):
    "Test ping with single switch topology (common code)."

    prompt = 'mininet>'

    def testCPU( self ):
        opts = [ '([a-z]+)\t([\d\.]+)%\t([\d\.]+)', pexpect.EOF ]
        p = pexpect.spawn( 'python -m mininet.examples.cpu' )
        scheds = []
        while True:
            index = p.expect( opts, timeout=600 )
            if index == 0:
                sched = p.match.group( 1 ) 
                cpu = float( p.match.group( 2 ) )
                bw = float( p.match.group( 3 ) )
                if sched not in scheds:
                    scheds.append( sched )
                    previous_bw = 10 ** 4 # 10 GB/s
                self.assertTrue( bw < previous_bw )
                previous_bw = bw
            else:
                break

        self.assertTrue( len( scheds ) > 0 )

if __name__ == '__main__':
    setLogLevel( 'warning' )
    unittest.main()
