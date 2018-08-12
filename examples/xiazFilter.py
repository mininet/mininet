#!/usr/bin/python

"""
xiazFilter.py: This example tests XIA multicasting with net-echo.
"""

from mininet.nodelib import LinuxBridge
from mininet.node import XIAHost
from mininet.net import Mininet
from mininet.cli import CLI
from mininet.log import setLogLevel, info


def zFilter():
    "The zFilter topology"

    net = Mininet()

    # zFilter ID for xia2
    zf = [ '0100000000000000000000000000000000000000' ]

    info( '*** Adding hosts\n' )
    xia1 = net.addHost( 'xia1' , cls=XIAHost, hid=[ 'xia1_hid1' ], xdp=True )
    xia2 = net.addHost( 'xia2' , cls=XIAHost, hid=[ 'xia2_hid1' ], zfid=zf,
                        xdp=True )
    xia3 = net.addHost( 'xia3' , cls=XIAHost, hid=[ 'xia3_hid1' ] )

    info( '*** Adding switch\n' )
    br1 = net.addSwitch( 'br1', cls=LinuxBridge )

    info( '*** Adding links\n' )
    net.addLink( xia1, br1 )
    net.addLink( xia2, br1 )
    net.addLink( xia3, br1 )

    info( '*** Starting network\n' )
    net.start()

    info( '*** Running CLI\n' )
    CLI( net )

    info( '*** Stopping network' )
    net.stop()

if __name__ == '__main__':
    setLogLevel( 'info' )
    zFilter()
