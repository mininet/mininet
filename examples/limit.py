#!/usr/bin/python

"""
limit.py: example of using link and CPU limits
"""

from mininet.net import Mininet
from mininet.link import TCIntf, Link
from mininet.node import CPULimitedHost
from mininet.topolib import TreeTopo
from mininet.util import custom, quietRun
from mininet.log import setLogLevel
from time import sleep

def testLinkLimit( net ):
    print '*** Testing network bandwidth limit'
    net.iperf()

def testCpuLimit( net ):
    print '*** Testing CPU bandwidth limit'
    h1, h2 = net.hosts
    h1.cmd( 'while true; do a=1; done &' )
    h2.cmd( 'while true; do a=1; done &' )
    pid1 = h1.cmd( 'echo $!' ).strip()
    pid2 = h2.cmd( 'echo $!' ).strip()
    cmd = 'ps -p %s,%s -o pid,%%cpu,args' % ( pid1, pid2 )
    for i in range( 0, 5):
        sleep( 1 ) 
        print quietRun( cmd )
    h1.cmd( 'kill %1')
    h2.cmd( 'kill %1')

def limit():
    "Example/test of link and CPU bandwidth limits"
    # 1 Mbps interfaces limited using tc
    intf1Mbps = custom( TCIntf, bw=1 )
    # Links consisting of two 10 Mbps interfaces
    link1Mbps = custom( Link, intf=intf1Mbps, cls2=TCIntf )
    # Hosts with 30% of system bandwidth
    host30pct = custom( CPULimitedHost, cpu=.3 )
    myTopo = TreeTopo( depth=1, fanout=2 )
    net = Mininet( topo=myTopo,
                   link=link1Mbps, 
                   host=host30pct )
    net.start()
    testLinkLimit( net )
    testCpuLimit( net )
    net.stop()

if __name__ == '__main__':
    setLogLevel( 'info' )
    limit()
