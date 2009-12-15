#!/usr/bin/python

"""
Create a 1024-host network, and run the CLI on it.
If this fails because of kernel limits, you may have
to adjust them, e.g. by adding entries to /etc/sysctl.conf
and running sysctl -p.
"""
   
from mininet.mininet import init, TreeNet, Cli

if __name__ == '__main__':
   init()
   network = TreeNet( depth=2, fanout=32, kernel=True )
   network.run( Cli )
