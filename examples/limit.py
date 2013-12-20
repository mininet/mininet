#!/usr/bin/python

"""
limit.py: example of using link and CPU limits
"""

from mininet.net import Mininet
from mininet.link import TCIntf
from mininet.node import CPULimitedHost
from mininet.topolib import TreeTopo
from mininet.util import custom
from mininet.log import setLogLevel


def testLinkLimit( net, bw ):
    """Run bandwidth limit test"""
    print '*** Testing network %.2f Mbps bandwidth limit' % bw
    net.iperf( )


def limit( bw=10, cpu=.1 ):
    """Example/test of link and CPU bandwidth limits
       bw: interface bandwidth limit in Mbps
       cpu: cpu limit as fraction of overall CPU time"""
    intf = custom( TCIntf, bw=bw )
    myTopo = TreeTopo( depth=1, fanout=2 )
    for sched in 'rt', 'cfs':
        print '*** Testing with', sched, 'bandwidth limiting'
        host = custom( CPULimitedHost, sched=sched, cpu=cpu )
        net = Mininet( topo=myTopo, intf=intf, host=host )
        net.start()
        testLinkLimit( net, bw=bw )
        net.runCpuLimitTest( cpu=cpu )
        net.stop()

def verySimpleLimit( bw=150 ):
    """Absurdly simple limiting test"""
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
    limit()
