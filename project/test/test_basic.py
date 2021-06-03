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


if __name__ == '__main__':
    setLogLevel('warning')
    unittest.main()
