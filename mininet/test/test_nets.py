#!/usr/bin/env python
'''@package mininet

Test creation and all-pairs ping for each included mininet topo type.
'''

from time import sleep
import unittest

from mininet.mininet import init, TreeNet, pingTest, DATAPATHS

class testMinimal(unittest.TestCase):
    '''For each datapath type, test ping with a minimal topology.

    Each topology has two hosts and one switch.
    '''

    def testMinimal(self):
        '''Ping test with user-space datapath on minimal topology'''
        init()
        for datapath in DATAPATHS:
            k = datapath == 'kernel'
            network = TreeNet(depth = 1, fanout = 2, kernel = k)
            dropped = network.run(pingTest)
            self.assertEqual(dropped, 0)


class testTree(unittest.TestCase):
    '''For each datapath type, test all-pairs ping with TreeNet.'''

    def testTree16(self):
        '''Ping test with user-space datapath on minimal topology'''
        init()
        for datapath in DATAPATHS:
            k = datapath == 'kernel'
            network = TreeNet(depth = 2, fanout = 4, kernel = k)
            dropped = network.run(pingTest)
            self.assertEqual(dropped, 0)


if __name__ == '__main__':
    unittest.main()