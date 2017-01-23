#!/usr/bin/python

"""
multiping.py: monitor multiple sets of hosts using ping

This demonstrates how one may send a simple shell script to
multiple hosts and monitor their output interactively for a period=
of time.
"""


from mininet.net import Mininet
from mininet.node import Node
from mininet.topo import SingleSwitchTopo
from mininet.log import info, setLogLevel

from select import poll, POLLIN
from time import time

def chunks( l, n ):
    "Divide list l into chunks of size n - thanks Stackoverflow"
    return [ l[ i: i + n ] for i in range( 0, len( l ), n ) ]

def startpings( host, targetips ):
    "Tell host to repeatedly ping targets"

    targetips = ' '.join( targetips )

    # Simple ping loop
    cmd = ( 'while true; do '
            ' for ip in %s; do ' % targetips +
            '  echo -n %s "->" $ip ' % host.IP() +
            '   `ping -c1 -w 1 $ip | grep packets` ;'
            '  sleep 1;'
            ' done; '
            'done &' )

    info( '*** Host %s (%s) will be pinging ips: %s\n' %
          ( host.name, host.IP(), targetips ) )

    host.cmd( cmd )

def multiping( netsize, chunksize, seconds):
    "Ping subsets of size chunksize in net of size netsize"

    # Create network and identify subnets
    topo = SingleSwitchTopo( netsize )
    net = Mininet( topo=topo )
    net.start()
    hosts = net.hosts
    subnets = chunks( hosts, chunksize )

    # Create polling object
    fds = [ host.stdout.fileno() for host in hosts ]
    poller = poll()
    for fd in fds:
        poller.register( fd, POLLIN )

    # Start pings
    for subnet in subnets:
        ips = [ host.IP() for host in subnet ]
        #adding bogus to generate packet loss
        ips.append( '10.0.0.200' )
        for host in subnet:
            startpings( host, ips )

    # Monitor output
    endTime = time() + seconds
    while time() < endTime:
        readable = poller.poll(1000)
        for fd, _mask in readable:
            node = Node.outToNode[ fd ]
            info( '%s:' % node.name, node.monitor().strip(), '\n' )

    # Stop pings
    for host in hosts:
        host.cmd( 'kill %while' )

    net.stop()


if __name__ == '__main__':
    setLogLevel( 'info' )
    multiping( netsize=20, chunksize=4, seconds=10 )
