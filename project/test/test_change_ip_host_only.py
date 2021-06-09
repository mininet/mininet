#!/usr/bin/env python

"""Project: Test Host Only
   Test changing ip on mininet interface and waiting zero drop pingAll results"""

import unittest
import sys
sys.path.append('..')

from custom_node import HostConnectedNode
from mininet.net import Mininet
from mininet.log import setLogLevel


class Test(unittest.TestCase):
    def testChangeIP(self):
        mn = Mininet(host=HostConnectedNode)

        h1 = mn.addHost('h1', inNamespace=True)
        h2 = mn.addHost('h2', inNamespace=True)
        s1 = mn.addSwitch('s1', inNamespace=False, failMode="standalone")

        mn.addLink(h1, s1)
        mn.addLink(h2, s1)

        mn.start()

        h2.config(ip="10.0.0.20")

        dropped = mn.pingAll()

        self.assertEqual(dropped, 0)

        mn.stop()


if __name__ == '__main__':
    # setLogLevel('debug')
    unittest.main()