#!/usr/bin/env python

"""
Test for emptynet.py
"""

import unittest
import pexpect
import sys

class testEmptyNet( unittest.TestCase ):

    prompt = u'mininet>'

    def testEmptyNet( self ):
        "Run simple CLI tests: pingall (verify 0% drop) and iperf (sanity)"
        p = pexpect.spawn( sys.executable + ' -m mininet.examples.emptynet', encoding='utf-8' )
        p.expect( self.prompt )
        # pingall test
        p.sendline( 'pingall' )
        p.expect ( u'(\d+)% dropped' )
        percent = int( p.match.group( 1 ) ) if p.match else -1
        self.assertEqual( percent, 0 )
        p.expect( self.prompt )
        # iperf test
        p.sendline( 'iperf' )
        p.expect( u"Results: \['[\d.]+ .bits/sec', '[\d.]+ .bits/sec'\]" )
        # p.expect( u"Results:" )

        p.expect( self.prompt )
        p.sendline( 'exit' )
        p.wait()

if __name__ == '__main__':
    unittest.main()
