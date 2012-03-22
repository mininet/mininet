#!/usr/bin/python

"""
limit.py: example of using link and CPU limits
"""

from mininet.net import Mininet
from mininet.link import TCIntf
from mininet.node import CPULimitedHost
from mininet.topolib import TreeTopo
from mininet.util import custom, quietRun
from mininet.log import setLogLevel
from time import sleep

def testLinkLimit( net, bw ):
    "Run bandwidth limit test"
    print '*** Testing network %.2f Mbps bandwidth limit' % bw
    net.iperf( )

def testCpuLimit( net, cpu ):
    "run CPU limit test"
    pct = cpu * 100
    print '*** Testing CPU %.0f%% bandwidth limit' % pct
    h1, h2 = net.hosts
    h1.cmd( 'while true; do a=1; done &' )
    h2.cmd( 'while true; do a=1; done &' )
    pid1 = h1.cmd( 'echo $!' ).strip()
    pid2 = h2.cmd( 'echo $!' ).strip()
    cmd = 'ps -p %s,%s -o pid,%%cpu,args' % ( pid1, pid2 )
    # It's a shame that this is what pylint prefers
    for _ in range( 5 ):
        sleep( 1 )
        print quietRun( cmd ).strip()
    h1.cmd( 'kill %1')
    h2.cmd( 'kill %1')

def limit( bw=10, cpu=.4 ):
    """Example/test of link and CPU bandwidth limits
       bw: interface bandwidth limit in Mbps
       cpu: cpu limit as fraction of overall CPU time"""
    intf = custom( TCIntf, bw=bw )
    myTopo = TreeTopo( depth=1, fanout=2 )
    for sched in 'rt', 'cfs':
        print '*** Testing with', sched, 'bandwidth limiting'
        host = custom( git CPULimitedHost, sched=sched, cpu=cpu )
        net = Mininet( topo=myTopo, intf=intf, host=host )
        net.start()
        testLinkLimit( net, bw=bw )
        testCpuLimit( net, cpu=cpu )
        net.stop()

def verySimpleLimit( bw=150 ):
    intf = custom( TCIntf, bw=bw )
    net = Mininet( intf=intf )
    h1, h2 = net.addHost( 'h1' ), net.addHost( 'h2' )
    net.addLink( h1, h2 )
    net.start()
    net.pingAll()
    net.iperf()
    h1.cmdPrint( 'tc -s qdisc ls dev', h1.defaultIntf() )
    h2.cmdPrint( 'tc -d class show dev', h2.defaultIntf() )
    h1.cmdPrint( 'tc -s qdisc ls dev', h1.defaultIntf() )
    h2.cmdPrint( 'tc -d class show dev', h2.defaultIntf() )
    net.stop()
    
if __name__ == '__main__':
    setLogLevel( 'info' )
    verySimpleLimit()
