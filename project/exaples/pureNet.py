#!/usr/bin/env python3
from mininet.cli import CLI
from mininet.link import Link
from mininet.net import Mininet
from mininet.log import setLogLevel
from mininet.node import Host, Controller, OVSSwitch
from mininet.nodelib import LinuxBridge

setLogLevel('info')

h1 = Host('h1', inNamespace=False)
h2 = Host('h2', inNamespace=False)
h3 = Host('h3', inNamespace=False)

s1 = OVSSwitch('s1', inNamespace=False)
c0 = Controller('c0', inNamespace=False, port=6666)

i1 = Link(h1, s1).intf1
i2 = Link(h2, s1).intf1
i3 = Link(h3, s1).intf1

h1.setIP('10.1/8', intf=i1)
h2.setIP('10.2/8', intf=i2)
h2.setIP('10.3/8', intf=i3)

c0.start()
s1.start([c0])
# s1.start([])

print(h1.cmd('ping -c2', h2.IP()))
print(h1.cmd('ping -c2', h3.IP()))
# s1.stop()
# c0.stop()
