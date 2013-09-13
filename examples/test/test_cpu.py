#!/usr/bin/env python

"""
Test for cpu.py
"""

import unittest
import pexpect
import sys

class testCPU( unittest.TestCase ):

    prompt = 'mininet>'

    @unittest.skipIf( '-quick' in sys.argv, 'long test' )
    def testCPU( self ):
        "Verify that CPU utilization is monotonically decreasing for each scheduler"
        p = pexpect.spawn( 'python -m mininet.examples.cpu' )
        opts = [ '([a-z]+)\t([\d\.]+)%\t([\d\.]+)', pexpect.EOF ]
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
    unittest.main()
