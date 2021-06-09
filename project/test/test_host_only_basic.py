#!/usr/bin/env python

"""Project: Test Host Only
   Test creation and all-pairs ping for each included mininet topo type."""

import unittest
import sys

sys.path.append('..')

from custom_node import HostConnectedNode
from mininet.topo import Topo
from mininet.net import Mininet
from mininet.log import setLogLevel


class SingleSwitchHostOnlyTopo(Topo):
    """Single switch connected to n hosts."""
    def build(self, n=2, **opts):
        switch = self.addSwitch('s1', inNamespace=False, failMode="standalone")

        for h in range(n):
            host = self.addHost(f'h{h + 1}', cls=HostConnectedNode, inNamespace=True)
            self.addLink(host, switch)


class Test(unittest.TestCase):
    mn = Mininet(topo=SingleSwitchHostOnlyTopo(), host=HostConnectedNode)

    def setUpModule(self):
        self.mn.start()

    def testSingle5(self):
        "Ping test on 5-host single-switch topology"
        dropped = self.mn.ping()
        self.assertEqual(dropped, 0)

    def testChangeIP(self):
        h2 = self.mn.getNodeByName("h2")
        h2.config(ip="10.0.0.20")
        dropped = self.mn.ping()
        self.assertEqual(dropped, 0)


if __name__ == '__main__':

    setLogLevel('debug')
    unittest.main()
