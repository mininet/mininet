#!/usr/bin/python

"""
cpu.py: test iperf bandwidth for varying cpu limits
"""

from mininet.net import Mininet
from mininet.node import CPULimitedHost
from mininet.topolib import TreeTopo
from mininet.util import custom
from mininet.log import setLogLevel, output

from time import sleep

def waitListening(client, server, port):
    "Wait until server is listening on port"
    if not client.cmd('which telnet'):
        raise Exception('Could not find telnet')
    cmd = ('sh -c "echo A | telnet -e A %s %s"' %
           (server.IP(), port))
    while 'Connected' not in client.cmd(cmd):
        output('waiting for', server,
               'to listen on port', port, '\n')
        sleep(.5)


def bwtest( cpuLimits, period_us=100000, seconds=5 ):
    """Example/test of link and CPU bandwidth limits
       cpu: cpu limit as fraction of overall CPU time"""

    topo = TreeTopo( depth=1, fanout=2 )

    results = {}

    for sched in 'rt', 'cfs':
        print '*** Testing with', sched, 'bandwidth limiting'
        for cpu in cpuLimits:
            host = custom( CPULimitedHost, sched=sched,
                           period_us=period_us,
                           cpu=cpu )
            net = Mininet( topo=topo, host=host )
            net.start()
            net.pingAll()
            hosts = [ net.getNodeByName( h ) for h in topo.hosts() ]
            client, server = hosts[ 0 ], hosts[ -1 ]
            server.cmd( 'iperf -s -p 5001 &' )
            waitListening( client, server, 5001 )
            result = client.cmd( 'iperf -yc -t %s -c %s' % (
                seconds, server.IP() ) ).split( ',' )
            bps = float( result[ -1 ] )
            server.cmdPrint( 'kill %iperf' )
            net.stop()
            updated = results.get( sched, [] )
            updated += [ ( cpu, bps ) ]
            results[ sched ] = updated

    return results


def dump( results ):
    "Dump results"

    fmt = '%s\t%s\t%s'

    print
    print fmt % ( 'sched', 'cpu', 'client MB/s' )
    print

    for sched in sorted( results.keys() ):
        entries = results[ sched ]
        for cpu, bps in entries:
            pct = '%.2f%%' % ( cpu * 100 )
            mbps = bps / 1e6
            print fmt % ( sched, pct, mbps )


if __name__ == '__main__':
    setLogLevel( 'info' )
    limits = [ .45, .4, .3, .2, .1 ]
    out = bwtest( limits )
    dump( out )
