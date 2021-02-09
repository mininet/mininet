#!/usr/bin/env python

"""
Regression test for pty leak in Node()
"""

import unittest

from mininet.net import Mininet
from mininet.clean import cleanup
from mininet.topo import SingleSwitchTopo

class TestPtyLeak( unittest.TestCase ):
    "Verify that there is no pty leakage"

    @staticmethod
    def testPtyLeak():
        "Test for pty leakage"
        net = Mininet( SingleSwitchTopo() )
        net.start()
        host = net[ 'h1' ]
        for _ in range( 0, 10 ):
            oldptys = host.slave, host.master
            net.delHost( host )
            host = net.addHost( 'h1' )
            assert ( host.slave, host.master ) == oldptys
        net.stop()


if __name__ == '__main__':
    unittest.main()
    cleanup()
