#!/usr/bin/env python

"""Project: Test Host Only
   Test creation and all-pairs ping for each included mininet topo type."""

import unittest

from custom_node import HostConnectedNode
from mininet.topo import SingleSwitchTopo
from mininet.net import Mininet
from utils import pingAllHostOnlyInf


class TestSingleSwitch(unittest.TestCase):
    def testPingMininet(self):
        "Ping test on 5-host single-switch topology"
        mn = Mininet(topo=SingleSwitchTopo(n=5), host=HostConnectedNode)
        mn.start()
        dropped = mn.ping()
        self.assertEqual(dropped, 0)
        mn.stop()

    def testPingHostOnly(self):
        "Ping test in local network on 5-host single-switch topology"
        mn = Mininet(topo=SingleSwitchTopo(n=5), host=HostConnectedNode)
        mn.start()
        dropped = pingAllHostOnlyInf(net=mn)
        self.assertEqual(dropped, 0)
        mn.stop()

    def testChangeIP(self):
        "Ping test in local and mininet network on 5-host single-switch topology after changing IP"
        mn = Mininet(topo=SingleSwitchTopo(n=5), host=HostConnectedNode)
        mn.start()
        h2 = mn.getNodeByName("h2")
        h2.config(ip="10.0.0.20")

        dropped = mn.pingAll()
        dropped_host_only = pingAllHostOnlyInf(net=mn)

        self.assertEqual(dropped, 0)
        self.assertEqual(dropped_host_only, 0)
        mn.stop()


if __name__ == '__main__':
    unittest.main()
