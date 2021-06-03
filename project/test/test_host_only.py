#!/usr/bin/env python

"""Project: Test Host Only
   Test creation and all-pairs ping for each included mininet topo type."""

import unittest
import sys
sys.path.insert(0, '..')

from custom_node import HostConnectedNode
from mininet.net import Mininet
from mininet.topo import SingleSwitchTopo
from mininet.log import setLogLevel
from mininet.clean import cleanup


class testHostOnly(unittest.TestCase):
    @staticmethod
    def tearDown():
        cleanup()

    def testSingle5(self):
        "Ping test on 5-host single-switch topology"
        mn = Mininet(host=HostConnectedNode, inNamespace=True)
        h1 = mn.addHost('h1', inNamespace=True)
        h2 = mn.addHost('h2', inNamespace=True)
        s1 = mn.addSwitch('s1', inNamespace=False, failMode="standalone")

        mn.addLink(h1, s1)
        mn.addLink(h2, s1)

        mn.start()

        dropped = mn.run(mn.ping)

        mn.stop()

        self.assertEqual(dropped, 0)

    def testChangeIP(self):
        mn = Mininet(host=HostConnectedNode, inNamespace=True, waitConnected=True)

        h1 = mn.addHost('h1', inNamespace=True)
        h2 = mn.addHost('h2', inNamespace=True)
        s1 = mn.addSwitch('s1', inNamespace=False, failMode="standalone")

        mn.addLink(h1, s1)
        mn.addLink(h2, s1)

        mn.start()

        h2.config(ip="10.0.0.20")

        dropped = mn.pingAll()

        mn.stop()
        self.assertEqual(dropped, 0)


    def testDropInterface(self):
        mn = Mininet(host=HostConnectedNode, inNamespace=True, waitConnected=True)

        h1 = mn.addHost('h1', inNamespace=True)
        h2 = mn.addHost('h2', inNamespace=True)
        s1 = mn.addSwitch('s1', inNamespace=False, failMode="standalone")

        mn.addLink(h1, s1)
        mn.addLink(h2, s1)

        mn.start()

        h2.intf(intf="h2-eth1").delete()

        dropped = mn.pingAll()

        mn.stop()
        self.assertEqual(dropped, 0)


if __name__ == '__main__':
    setLogLevel('warning')
    unittest.main()
