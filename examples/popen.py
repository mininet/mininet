#!/usr/bin/env python

"""
This example monitors a number of hosts using host.popen() and
pmonitor()
"""

from mininet.net import Mininet
from mininet.topo import SingleSwitchTopo
from mininet.log import setLogLevel, info
from mininet.util import pmonitor

def monitorhosts( hosts=5 ):
    "Start a bunch of pings and monitor them using popen"
    mytopo = SingleSwitchTopo( hosts )
    net = Mininet( topo=mytopo, waitConnected=True )
    net.start()
    # Start a bunch of pings
    popens = {}
    last = net.hosts[ -1 ]
    for host in net.hosts:
        popens[ host ] = host.popen( "ping -c5 %s" % last.IP() )
        last = host
    # Monitor them and print output
    for host, line in pmonitor( popens ):
        if host:
            info( "<%s>: %s" % ( host.name, line ) )
    # Done
    net.stop()


if __name__ == '__main__':
    setLogLevel( 'info' )
    monitorhosts( hosts=5 )
