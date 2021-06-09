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
from mininet.log import info, error, debug, output, warn
from mininet.log import setLogLevel


def pingHostOnlyInf(self, hosts=None, timeout=None):
    """Ping between all specified hosts.
       hosts: list of hosts
       timeout: time to wait for a response, as string
       returns: ploss packet loss percentage"""
    # should we check if running?
    packets = 0
    lost = 0
    ploss = None
    if not hosts:
        hosts = self.hosts
        output('*** Ping: testing ping reachability\n')
    for node in hosts:
        output('%s -> ' % node.name)
        for dest in hosts:
            if node != dest:
                opts = ''
                if timeout:
                    opts = '-W %s' % timeout
                if dest.intfs:
                    result = node.cmd(f"ping -c1 {opts} -I {node.getHostOnlyIntf()} {dest.IP(intf=dest.getHostOnlyIntf())}")
                    sent, received = self._parsePing(result)
                else:
                    sent, received = 0, 0
                packets += sent
                if received > sent:
                    error('*** Error: received too many packets')
                    error('%s' % result)
                    node.cmdPrint('route')
                    exit(1)
                lost += sent - received
                output(('%s ' % dest.name) if received else 'X ')
        output('\n')
    if packets > 0:
        ploss = 100.0 * lost / packets
        received = packets - lost
        output("*** Results: %i%% dropped (%d/%d received)\n" %
               (ploss, received, packets))
    else:
        ploss = 0
        output("*** Warning: No packets sent\n")
    return ploss


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