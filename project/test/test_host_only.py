#!/usr/bin/env python

"""Project: Test Host Only
   Test Encapsulation test"""

import unittest
import sys
sys.path.append('..')

from custom_node import HostConnectedNode
from mininet.net import Mininet
from mininet.node import Host
from mininet.clean import cleanup
from mininet.log import setLogLevel


class Test(unittest.TestCase):
    @staticmethod
    def tearDown():
        cleanup()

    def testChangeIP(self):
        mn = Mininet()

        h1 = mn.addHost('h1', inNamespace=True, cls=HostConnectedNode)
        h2 = mn.addHost('h2', inNamespace=True, cls=HostConnectedNode)
        h3 = mn.addHost('h3', inNamespace=True, cls=HostConnectedNode)
        h4 = mn.addHost('h4', inNamespace=True, cls=Host)
        s1 = mn.addSwitch('s1', inNamespace=False, failMode="standalone")

        mn.addLink(h4, s1)
        mn.addLink(h3, s1)

        mn.start()
        dropped_h3_h4 = mn.ping(hosts=[h3, h4])
        dropped_h1_h2_h3 = mn.ping(hosts=[h1, h2, h3])
        self.assertEqual(dropped_h3_h4, 0)
        self.assertEqual(dropped_h1_h2_h3, 0)

        mn.stop()


if __name__ == '__main__':
    # setLogLevel('debug')
    unittest.main()