'''Example of custom topo

@author Brandon Heller (brandonh@stanford.edu)

'''

from mininet.topo import SingleSwitchTopo
from mininet.net import Mininet
from mininet.node import KernelSwitch, Host, Controller, ControllerParams

topo = SingleSwitchTopo(k = 2) # build topology object
switch = KernelSwitch
host = Host
controller = Controller
controller_params = ControllerParams(0x0a000000, 8) # 10.0.0.0/8
in_namespace = False
xterms = False
mac = True
arp = True

mn = Mininet(topo, switch, host, controller, controller_params,
             in_namespace = in_namespace,
             xterms = xterms, auto_set_macs = mac,
             auto_static_arp = arp)

