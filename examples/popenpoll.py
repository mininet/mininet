#!/usr/bin/python

"Monitor multiple hosts using popen()/pmonitor()"

from mininet.net import Mininet
from mininet.topo import SingleSwitchTopo
from mininet.util import pmonitor
from time import time
from signal import SIGINT

def pmonitorTest( N=3, seconds=10 ):
    "Run pings and monitor multiple hosts using pmonitor"
    topo = SingleSwitchTopo( N )
    net = Mininet( topo )
    net.start()
    hosts = net.hosts
    print "Starting test..."
    server = hosts[ 0 ]
    popens = {}
    for h in hosts:
        popens[ h ] = h.popen('ping', server.IP() )
    print "Monitoring output for", seconds, "seconds"
    endTime = time() + seconds
    for h, line in pmonitor( popens, timeoutms=500 ):
        if h:
            print '<%s>: %s' % ( h.name, line ),
        if time() >= endTime:
            for p in popens.values():
                p.send_signal( SIGINT )
    net.stop()

if __name__ == '__main__':
    pmonitorTest()
