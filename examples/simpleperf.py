#!/usr/bin/python

"""
Simple example of setting network and CPU parameters
"""

from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import CPULimitedHost
from mininet.link import TCLink
from mininet.util import dumpNodeConnections
from mininet.log import setLogLevel

class SingleSwitchTopo(Topo):
   "Single switch connected to n hosts."
   def __init__(self, n=2, **opts):
       Topo.__init__(self, **opts)
       switch = self.add_switch('s1')
       for h in range(n+1):
        # Each host gets 50%/n of system CPU
           host = self.add_host('h%s' % (h + 1),
            cpu=.5/n)
        # 10 Mbps, 5ms delay, 10% loss
           self.add_link(host, switch,
            bw=10, delay='5ms', loss=10, use_htb=True)

def perfTest():
   "Create network and run simple performance test"
   topo = SingleSwitchTopo(n=4)
   net = Mininet(topo=topo,
                 host=CPULimitedHost, link=TCLink)
   net.start()
   print "Dumping host connections"
   dumpNodeConnections(net.hosts)
   print "Testing network connectivity"
   net.pingAll()
   print "Testing bandwidth between h1 and h4"
   h1 = net.getNodeByName('h1')
   h4 = net.getNodeByName('h4')
   net.iperf((h1, h4))
   net.stop()

if __name__ == '__main__':
   setLogLevel('info')
   perfTest()
