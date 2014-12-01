#!/usr/bin/env python

"""
Test for cpu.py

results format:

    sched   cpu client MB/s

    cfs 45.00%  13254.669841
    cfs 40.00%  11822.441399
    cfs 30.00%  5112.963009
    cfs 20.00%  3449.090009
    cfs 10.00%  2271.741564

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
        # matches each line from results( shown above )
        opts = [ '([a-z]+)\t([\d\.]+)%\t([\d\.]+)',
                 pexpect.EOF ]
        scheds = []
        while True:
            index = p.expect( opts, timeout=600 )
            if index == 0:
                sched = p.match.group( 1 )
                cpu = float( p.match.group( 2 ) )
                bw = float( p.match.group( 3 ) )
                if sched not in scheds:
                    scheds.append( sched )
                else:
                    self.assertTrue( bw < previous_bw )
                previous_bw = bw
            else:
                break

        self.assertTrue( len( scheds ) > 0 )

if __name__ == '__main__':
    unittest.main()
