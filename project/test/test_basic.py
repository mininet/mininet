#!/usr/bin/env python

"""Project: Test basic
   Test creation and all-pairs ping for each included mininet topo type."""

import unittest

from mininet.net import Mininet
from mininet.topo import SingleSwitchTopo
from mininet.log import setLogLevel
from mininet.clean import cleanup


class testBasic(unittest.TestCase):
    @staticmethod
    def tearDown():
        cleanup()

    def testSingle5(self):
        "Ping test on 5-host single-switch topology"
        mn = Mininet(SingleSwitchTopo(k=5), waitConnected=True)
        dropped = mn.run(mn.ping)
        self.assertEqual(dropped, 0)

    def testChangeIP(self):
        mn = Mininet(SingleSwitchTopo(k=5))
        mn.start()

        h1, h2, h3, h4, h5 = mn.hosts
        h5.config(ip="10.0.0.20")
        dropped = mn.pingAll()
        self.assertEqual(dropped, 0)

        mn.stop()

    def testDropInterface(self):
        mn = Mininet(SingleSwitchTopo(k=5))
        mn.start()

        h1, h2, h3, h4, h5 = mn.hosts
        h5.intf(intf="h5-eth0").delete()
        dropped = mn.ping(hosts=[h5, h4])
        self.assertEqual(dropped, 100)

        mn.stop()


if __name__ == '__main__':
    setLogLevel('warning')
    unittest.main()
