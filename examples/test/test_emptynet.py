#!/usr/bin/env python

"""
Test for emptynet.py
"""

import unittest
from mininet.util import pexpect

class testEmptyNet( unittest.TestCase ):

    prompt = 'mininet>'

    def testEmptyNet( self ):
        "Run simple CLI tests: pingall (verify 0% drop) and iperf (sanity)"
        p = pexpect.spawn( 'python -m mininet.examples.emptynet' )
        p.expect( self.prompt )
        # pingall test
        p.sendline( 'pingall' )
        p.expect ( '(\d+)% dropped' )
        percent = int( p.match.group( 1 ) ) if p.match else -1
        self.assertEqual( percent, 0 )
        p.expect( self.prompt )
        # iperf test
        p.sendline( 'iperf' )
        p.expect( "Results: \['[\d.]+ .bits/sec', '[\d.]+ .bits/sec'\]" )
        p.expect( self.prompt )
        p.sendline( 'exit' )
        p.wait()

if __name__ == '__main__':
    unittest.main()
