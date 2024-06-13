#!/usr/bin/python

"""
Create a simple, star topology and gratuitiously ARP from each host,
which may aid in a network controller's host discovery. However, these
ARPs will not populate the ARP tables of the other hosts.

This can also be done from the Mininet CLI:
mininet> py [ h.cmd('arping -U -c 1 ' + h.IP()) for h in net.hosts ]
"""

from mininet.log import setLogLevel
from mininet.util import quietRun
from mininet.log import error
from mininet.cli import CLI
from mininet.net import Mininet
from mininet.topo import SingleSwitchTopo

if __name__ == '__main__':

    if not quietRun( 'which arping' ):
        error( "Cannot find command 'arping'\nThe package",
               "'iputils-arping' is required in Ubuntu or Debian\n" )
        exit()
    
    setLogLevel( 'info' )

    net = Mininet( topo=SingleSwitchTopo( k=10 ), waitConnected=True )
    net.start()

    for host in net.hosts:
        print host
        print host.cmd( 'arping -U -c 1 ' + host.IP() )

    CLI( net )
    net.stop()
