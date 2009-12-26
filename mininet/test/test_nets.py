#!/usr/bin/env python
'''@package mininet

Test creation and all-pairs ping for each included mininet topo type.
'''

from time import sleep
import unittest

from mininet.net import init, Mininet #, DATAPATHS
from mininet.node import Switch, Host, NOXController, ControllerParams
from mininet.node import Controller
from mininet.topo import TreeTopo

# temporary, until user-space side is tested
DATAPATHS = ['kernel']

class testMinimal(unittest.TestCase):
    '''For each datapath type, test ping with a minimal topology.

    Each topology has two hosts and one switch.
    '''

    def testMinimal(self):
        '''Ping test with both datapaths on minimal topology'''
        init()
        for datapath in DATAPATHS:
            k = datapath == 'kernel'
            controller_params = ControllerParams(0x0a000000, 8) # 10.0.0.0/8
            mn = Mininet(TreeTopo(), Switch, Host, Controller,
                         controller_params)
            mn.start()
            dropped = mn.ping_test()
            self.assertEqual(dropped, 0)
            mn.stop()


class testTree(unittest.TestCase):
    '''For each datapath type, test all-pairs ping with TreeNet.'''

    def testTree16(self):
        '''Ping test with both datapaths on 16-host topology'''
        init()
        for datapath in DATAPATHS:
            k = datapath == 'kernel'
            controller_params = ControllerParams(0x0a000000, 8) # 10.0.0.0/8
            tree_topo = TreeTopo(depth = 3, fanout = 4)
            mn = Mininet(tree_topo, Switch, Host, Controller,
                         controller_params)
            mn.start()
            dropped = mn.ping_test()
            self.assertEqual(dropped, 0)
            mn.stop()

#class testLinear(unittest.TestCase):
#    '''For each datapath type, test all-pairs ping with LinearNet.'''
#
#    def testLinear10(self):
#        '''Ping test  with both datapaths on 10-switch topology'''
#        init()
#        for datapath in DATAPATHS:
#             k = datapath == 'kernel'
#             network = network = LinearNet(10, kernel=k)
#             dropped = network.run(pingTest)
#             self.assertEqual(dropped, 0)


if __name__ == '__main__':
    unittest.main()