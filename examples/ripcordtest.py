#!/usr/bin/python
'''Run a FatTree network from the Ripcord project.'''

from ripcord.topo import FatTreeTopo

from mininet.logging_mod import set_loglevel
from mininet.net import init, Mininet
from mininet.node import Switch, Host, NOXController, ControllerParams

if __name__ == '__main__':
    set_loglevel('info')
    init()
    controller_params = ControllerParams(0x0a000000, 8) # 10.0.0.0/8
    mn = Mininet(FatTreeTopo(4), Switch, Host, NOXController,
                 controller_params)
    mn.interact()