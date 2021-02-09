#!/usr/bin/env python

"""
Test for cpu.py

results format:

sched	cpu	received bits/sec
cfs	50%	8.14e+09
cfs	40%	6.48e+09
cfs	30%	4.56e+09
cfs	20%	2.84e+09
cfs	10%	1.29e+09

"""

import unittest
from mininet.util import pexpect
import sys

class testCPU( unittest.TestCase ):

    prompt = 'mininet>'

    @unittest.skipIf( '-quick' in sys.argv, 'long test' )
    def testCPU( self ):
        "Verify that CPU utilization is monotonically decreasing for each scheduler"
        p = pexpect.spawn( 'python -m mininet.examples.cpu', timeout=300 )
        # matches each line from results( shown above )
        opts = [ '([a-z]+)\t([\d\.]+)%\t([\d\.e\+]+)',
                 pexpect.EOF ]
        scheds = []
        while True:
            index = p.expect( opts )
            if index == 0:
                sched = p.match.group( 1 )
                cpu = float( p.match.group( 2 ) )
                bw = float( p.match.group( 3 ) )
                if sched not in scheds:
                    scheds.append( sched )
                else:
                    self.assertTrue( bw < previous_bw,
                                     "%e should be less than %e\n" %
                                     ( bw, previous_bw ) )
                previous_bw = bw
            else:
                break

        self.assertTrue( len( scheds ) > 0 )

if __name__ == '__main__':
    unittest.main()
