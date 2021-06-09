#!/usr/bin/env python

"""Project: Test Host Only
   Test creation and all-pairs ping for each included mininet topo type."""

import unittest
import sys

sys.path.append('..')

from custom_node import HostConnectedNode
from mininet.topo import Topo, SingleSwitchTopo
from mininet.net import Mininet
from mininet.log import error, output


def pingAllHostOnlyInf(net, hosts=None, timeout=None):
    """Ping between all specified hosts.
       hosts: list of hosts
       timeout: time to wait for a response, as string
       returns: ploss packet loss percentage"""
    # should we check if running?
    packets = 0
    lost = 0
    ploss = None
    if not hosts:
        hosts = net.hosts
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
                    sent, received = net._parsePing(result)
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
