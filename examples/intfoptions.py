#!/usr/bin/python

'''
example of using various TCIntf options.
reconfigures a single interface using intf.config()
to use different traffic control commands to test
bandwidth, loss, and delay
'''

from mininet.net import Mininet
from mininet.log import setLogLevel, info
from mininet.link import TCLink

def intfOptions():
    "run various traffic control commands on a single interface"
    net = Mininet( autoStaticArp=True )
    net.addController( 'c0' )
    h1 = net.addHost( 'h1' )
    h2 = net.addHost( 'h2' )
    s1 = net.addSwitch( 's1' )
    link1 = net.addLink( h1, s1, cls=TCLink )
    net.addLink( h2, s1 )
    net.start()

    # flush out latency from reactive forwarding delay
    net.pingAll()

    info( '\n*** Configuring one intf with bandwidth of 5 Mb\n' )
    link1.intf1.config( bw=5 )
    info( '\n*** Running iperf to test\n' )
    net.iperf()

    info( '\n*** Configuring one intf with loss of 50%\n' )
    link1.intf1.config( loss=50 )
    info( '\n' )
    net.iperf( ( h1, h2 ), l4Type='UDP' )

    info( '\n*** Configuring one intf with delay of 15ms\n' )
    link1.intf1.config( delay='15ms' )
    info( '\n*** Run a ping to confirm delay\n' )
    net.pingPairFull()

    info( '\n*** Done testing\n' )
    net.stop()

if __name__ == '__main__':
    setLogLevel( 'info' )
    intfOptions()
