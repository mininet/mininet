#!/usr/bin/env python

"""Package: mininet
   Test creation and pings for topologies with link and/or CPU options."""

import unittest

from mininet.net import Mininet
from mininet.node import OVSKernelSwitch
from mininet.topo import Topo
from mininet.log import setLogLevel


SWITCH = OVSKernelSwitch
# Number of hosts for each test
N = 2


class SingleSwitchOptionsTopo(Topo):
    "Single switch connected to n hosts."
    def __init__(self, n=2, hopts={}, lopts={}):
        Topo.__init__(self, hopts=hopts, lopts=lopts)
        switch = self.addSwitch('s1')
        for h in range(n):
            host = self.addHost('h%s' % (h + 1))
            self.addLink(host, switch)


class testOptionsTopo( unittest.TestCase ):
    "Verify ability to create networks with host and link options."

    def runOptionsTopoTest( self, n, hopts=None, lopts=None ):
        "Generic topology-with-options test runner."
        mn = Mininet( SingleSwitchOptionsTopo( n=n, hopts=hopts ) )
        dropped = mn.run( mn.ping )
        self.assertEqual( dropped, 0 )

    def testCPULimits( self ):
        hopts = { 'cpu': 0.5 / N }
        self.runOptionsTopoTest(N, hopts=hopts)

    def testLinkBandwidth( self ):
        lopts = { 'bw': 10, 'use_htb': True }
        self.runOptionsTopoTest(N, lopts=lopts)

    def testLinkDelay( self ):
        lopts = { 'delay': '5ms', 'use_htb': True }
        self.runOptionsTopoTest(N, lopts=lopts)

    def testLinkLoss( self ):
        lopts = { 'loss': 10, 'use_htb': True }
        self.runOptionsTopoTest(N, lopts=lopts)

    def testAllOptions( self ):
        lopts = { 'bw': 10, 'delay': '5ms', 'loss': 10, 'use_htb': True }
        hopts = { 'cpu': 0.5 / N }
        self.runOptionsTopoTest(N, hopts=hopts, lopts=lopts)



if __name__ == '__main__':
    setLogLevel( 'warning' )
    unittest.main()
