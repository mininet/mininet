#!/usr/bin/env python

"clusterperf.py compare the maximum throughput between SSH and GRE tunnels"

from mininet.examples.cluster import RemoteSSHLink, RemoteGRELink, RemoteHost
from mininet.net import Mininet
from mininet.log import setLogLevel

def perf(Link):
    "Test connectivity nand performance over Link"
    net = Mininet( host=RemoteHost, link=Link, waitConnected=True )
    h1 = net.addHost( 'h1')
    h2 = net.addHost( 'h2', server='ubuntu2' )
    net.addLink( h1, h2 )
    net.start()
    net.pingAll()
    net.iperf()
    net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    perf( RemoteSSHLink )
    perf( RemoteGRELink )
