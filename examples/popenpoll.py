#!/usr/bin/env python

"Monitor multiple hosts using popen()/pmonitor()"

from time import time
from signal import SIGINT

from mininet.net import Mininet
from mininet.topo import SingleSwitchTopo
from mininet.util import pmonitor
from mininet.log import setLogLevel, info


def pmonitorTest( N=3, seconds=10 ):
    "Run pings and monitor multiple hosts using pmonitor"
    topo = SingleSwitchTopo( N )
    net = Mininet( topo, waitConnected=True )
    net.start()
    hosts = net.hosts
    info( "Starting test...\n" )
    server = hosts[ 0 ]
    popens = {}
    for h in hosts:
        popens[ h ] = h.popen('ping', server.IP() )
    info( "Monitoring output for", seconds, "seconds\n" )
    endTime = time() + seconds
    for h, line in pmonitor( popens, timeoutms=500 ):
        if h:
            info( '<%s>: %s' % ( h.name, line ) )
        if time() >= endTime:
            for p in popens.values():
                p.send_signal( SIGINT )
    net.stop()


if __name__ == '__main__':
    setLogLevel( 'info' )
    pmonitorTest()
