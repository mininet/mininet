#!/usr/bin/env python

"""
Create a network with 5 hosts, numbered 1-4 and 9.
Validate that the port numbers match to the interface name,
and that the ovs ports match the mininet ports.
"""


from mininet.net import Mininet
from mininet.node import Controller
from mininet.log import setLogLevel, info, warn

def validatePort( switch, intf ):
    "Validate intf's OF port number"
    ofport = int( switch.cmd( 'ovs-vsctl get Interface', intf,
                              'ofport' ) )
    if ofport != switch.ports[ intf ]:
        warn( 'WARNING: ofport for', intf, 'is actually', ofport, '\n' )
        return 0
    else:
        return 1

def testPortNumbering():

    """Test port numbering:
       Create a network with 5 hosts (using Mininet's
       mid-level API) and check that implicit and
       explicit port numbering works as expected."""

    net = Mininet( controller=Controller, waitConnected=True )

    info( '*** Adding controller\n' )
    net.addController( 'c0' )

    info( '*** Adding hosts\n' )
    h1 = net.addHost( 'h1', ip='10.0.0.1' )
    h2 = net.addHost( 'h2', ip='10.0.0.2' )
    h3 = net.addHost( 'h3', ip='10.0.0.3' )
    h4 = net.addHost( 'h4', ip='10.0.0.4' )
    h5 = net.addHost( 'h5', ip='10.0.0.5' )

    info( '*** Adding switch\n' )
    s1 = net.addSwitch( 's1' )

    info( '*** Creating links\n' )
    # host 1-4 connect to ports 1-4 on the switch
    net.addLink( h1, s1 )
    net.addLink( h2, s1 )
    net.addLink( h3, s1 )
    net.addLink( h4, s1 )
    # specify a different port to connect host 5 to on the switch.
    net.addLink( h5, s1, port1=1, port2= 9)

    info( '*** Starting network\n' )
    net.start()

    # print the interfaces and their port numbers
    info( '\n*** printing and validating the ports '
          'running on each interface\n' )
    for intfs in s1.intfList():
        if not intfs.name == "lo":
            info( intfs, ': ', s1.ports[intfs],
                  '\n' )
            info( 'Validating that', intfs,
                   'is actually on port', s1.ports[intfs], '... ' )
            if validatePort( s1, intfs ):
                info( 'Validated.\n' )
    info( '\n' )

    # test the network with pingall
    net.pingAll()
    info( '\n' )

    info( '*** Stopping network\n' )
    net.stop()


if __name__ == '__main__':
    setLogLevel( 'info' )
    testPortNumbering()
