#!/usr/bin/python

"""
Create a tree network and run udpbwtest.c on it, attempting to
saturate global bandwidth by sending constant all-to-all
udp traffic. This should be something of a stress test.

We should also make a tcp version. :D

In addition to trying to saturate global bandwidth in
various Mininet configurations, this example:

- uses a topology, TreeTopo, from mininet.topolib
- starts up a custom test program, udpbwtest, on each host
- dynamically monitors the output of a set of hosts

"""

import os
import re
import sys
from time import time

flush = sys.stdout.flush

from mininet.log import lg
from mininet.net import Mininet
from mininet.node import KernelSwitch
from mininet.topolib import TreeTopo
from mininet.util import quietRun

# bwtest support

def parsebwtest( line,
    r=re.compile( r'(\d+) s: in ([\d\.]+) MB/s, out ([\d\.]+) MB/s' ) ):
    "Parse udpbwtest.c output, returning seconds, inbw, outbw."
    match = r.match( line )
    if match:
        seconds, inbw, outbw = match.group( 1, 2, 3 )
        return int( seconds ), float( inbw ), float( outbw )
    return None, None, None

def printTotalHeader():
    "Print header for bandwidth stats."
    print
    print "time(s)\thosts\ttotal in/out (MB/s)\tavg in/out (MB/s)"

# Annoyingly, pylint isn't smart enough to notice
# when an unused variable is an iteration tuple
# pylint: disable-msg=W0612

def printTotal( seconds=None, result=None ):
    "Compute and print total bandwidth for given results set."
    intotal = outtotal = 0.0
    count = len( result )
    for host, inbw, outbw in result:
        intotal += inbw
        outtotal += outbw
    inavg = intotal / count if count > 0 else 0
    outavg = outtotal / count if count > 0 else 0
    print '%d\t%d\t%.2f/%.2f\t\t%.2f/%.2f' % ( seconds, count,
        intotal, outtotal, inavg, outavg )

# pylint: enable-msg=W0612

# Pylint also isn't smart enough to understand iterator.next()
# pylint: disable-msg=E1101

def udpbwtest( net, seconds ):
    "Start up and monitor udpbwtest on each of our hosts."
    hosts = net.hosts
    hostCount = len( hosts )
    print "*** Starting udpbwtest on hosts"
    for host in hosts:
        ips = [ h.IP() for h in hosts if h != host ]
        print host.name,
        flush()
        host.cmd( './udpbwtest ' + ' '.join( ips ) + ' &' )
    print
    results = {}
    print "*** Monitoring hosts"
    output = net.monitor( hosts )
    quitTime = time() + seconds
    while time() < quitTime:
        host, line = output.next()
        if host is None:
            break
        seconds, inbw, outbw = parsebwtest( line )
        if seconds is not None:
            result = results.get( seconds, [] ) + [ ( host, inbw, outbw ) ]
            if len( result ) == hostCount:
                printTotal( seconds, result )
            results[ seconds ] = result
    print "*** Stopping udpbwtest processes"
    # We *really* don't want these things hanging around!
    quietRun( 'killall -9 udpbwtest' )
    print
    print "*** Results:"
    printTotalHeader()
    times = sorted( results.keys() )
    for t in times:
        printTotal( t - times[ 0 ] , results[ t ] )
    print

# pylint: enable-msg=E1101

if __name__ == '__main__':
    lg.setLogLevel( 'info' )
    if not os.path.exists( './udpbwtest' ):
        raise Exception( 'Could not find udpbwtest in current directory.' )
    network = Mininet( TreeTopo( depth=1, fanout=8 ), switch=KernelSwitch )
    network.start()
    udpbwtest( network, seconds=10 )
    network.stop()
