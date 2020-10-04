#!/usr/bin/python                                                                            
                                                                                             
from mininet.topo import Topo
from mininet.net import Mininet
from mininet.util import dumpNodeConnections
from mininet.log import setLogLevel

class SingleSwitchTopo(Topo):
    "4 switches and 32 hosts."
    def build(self, n=2):
        switch = self.addSwitch('s1')
		for s in range(4):
            switch = self.addSwitch('s%s' % (s + 1))
			
        for h in range(32):
            host = self.addHost('h%s' % (h + 1))
			
            self.addLink(host, switch)