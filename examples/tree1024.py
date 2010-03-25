#!/usr/bin/python

"""
Create a 1024-host network, and run the CLI on it.
If this fails because of kernel limits, you may have
to adjust them, e.g. by adding entries to /etc/sysctl.conf
and running sysctl -p. Check util/sysctl_addon.
"""

from mininet.cli import CLI
from mininet.log import setLogLevel
from mininet.net import init, Mininet
from mininet.node import KernelSwitch
from mininet.topolib import TreeTopo

def TreeNet( depth=1, fanout=2, **kwargs ):
    "Convenience function for creating tree networks."
    topo = TreeTopo( depth, fanout )
    return Mininet( topo, **kwargs )

if __name__ == '__main__':
    setLogLevel( 'info' )
    init()
    KernelSwitch.setup()
    network = TreeNet( depth=2, fanout=32, switch=KernelSwitch )
    network.run( CLI, network )
