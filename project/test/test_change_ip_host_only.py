#!/usr/bin/env python

"""Project: Test Host Only
   Test changing ip on mininet interface and waiting zero drop pingAll results"""

import unittest
import sys
sys.path.append('..')

from custom_node import HostConnectedNode
from mininet.net import Mininet
from mininet.log import error, output
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
    def testChangeIP(self):
        mn = Mininet(host=HostConnectedNode)

        h1 = mn.addHost('h1', inNamespace=True)
        h2 = mn.addHost('h2', inNamespace=True)
        s1 = mn.addSwitch('s1', inNamespace=False, failMode="standalone")

        mn.addLink(h1, s1)
        mn.addLink(h2, s1)

        mn.start()
        dropped = mn.pingAll()
        h2.config(ip="10.0.0.20")

        dropped_host_only = pingHostOnlyInf()

        self.assertEqual(dropped, 0)
        self.assertEqual(dropped_host_only, 0)
        mn.stop()


if __name__ == '__main__':
    # setLogLevel('debug')
    unittest.main()