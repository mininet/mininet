#!/usr/bin/env python

"""
natnet.py: Example network with NATs


           h0
           |
           s0
           |
    ----------------
    |              |
   nat1           nat2
    |              |
   s1              s2
    |              |
   h1              h2

"""

from mininet.topo import Topo
from mininet.net import Mininet
from mininet.nodelib import NAT
from mininet.log import setLogLevel
from mininet.cli import CLI
from mininet.util import irange

class InternetTopo(Topo):
    "Single switch connected to n hosts."
    # pylint: disable=arguments-differ
    def build(self, n=2, **_kwargs ):
        # set up inet switch
        inetSwitch = self.addSwitch('s0')
        # add inet host
        inetHost = self.addHost('h0')
        self.addLink(inetSwitch, inetHost)

        # add local nets
        for i in irange(1, n):
            inetIntf = 'nat%d-eth0' % i
            localIntf = 'nat%d-eth1' % i
            localIP = '192.168.%d.1' % i
            localSubnet = '192.168.%d.0/24' % i
            natParams = { 'ip' : '%s/24' % localIP }
            # add NAT to topology
            nat = self.addNode('nat%d' % i, cls=NAT, subnet=localSubnet,
                               inetIntf=inetIntf, localIntf=localIntf)
            switch = self.addSwitch('s%d' % i)
            # connect NAT to inet and local switches
            self.addLink(nat, inetSwitch, intfName1=inetIntf)
            self.addLink(nat, switch, intfName1=localIntf, params1=natParams)
            # add host and connect to local switch
            host = self.addHost('h%d' % i,
                                ip='192.168.%d.100/24' % i,
                                defaultRoute='via %s' % localIP)
            self.addLink(host, switch)

def run():
    "Create network and run the CLI"
    topo = InternetTopo()
    net = Mininet(topo=topo, waitConnected=True )
    net.start()
    CLI(net)
    net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    run()
