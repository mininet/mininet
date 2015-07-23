#!/usr/bin/python

from mininet.net import Mininet
from mininet.node import Controller, RemoteController
from mininet.cli import CLI
from mininet.log import setLogLevel, info

def emptyNet():

    NODE2_IP='192.168.56.103'
    CONTROLLER_IP='192.168.56.103'

    net = Mininet( topo=None,
                   build=False)

    net.addController( 'c0',
                      controller=RemoteController,
                      ip=CONTROLLER_IP,
                      port=6633)

    h1 = net.addHost( 'h1', ip='10.0.0.1' )
    h2 = net.addHost( 'h2', ip='10.0.0.2' )
    s1 = net.addSwitch( 's1' )
    net.addLink( h1, s1 )
    net.addLink( h2, s1 )
    net.start()

    # Configure the GRE tunnel
    s1.cmd('ovs-vsctl add-port s1 s1-gre1 -- set interface s1-gre1 type=gre options:remote_ip='+NODE2_IP)
    s1.cmdPrint('ovs-vsctl show')

    CLI( net )
    net.stop()

if __name__ == '__main__':
    setLogLevel( 'info' )
    emptyNet()
