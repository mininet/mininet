#!/usr/bin/python

"""
Simple example of sending output to multiple files and
monitoring them
"""


from mininet.topo import SingleSwitchTopo
from mininet.net import Mininet
from mininet.log import info, setLogLevel

from time import time
from select import poll, POLLIN
from subprocess import Popen, PIPE


def monitorFiles( outfiles, seconds, timeoutms ):
    "Monitor set of files and return [(host, line)...]"
    devnull = open( '/dev/null', 'w' )
    tails, fdToFile, fdToHost = {}, {}, {}
    for h, outfile in outfiles.iteritems():
        tail = Popen( [ 'tail', '-f', outfile ],
                      stdout=PIPE, stderr=devnull )
        fd = tail.stdout.fileno()
        tails[ h ] = tail
        fdToFile[ fd ] = tail.stdout
        fdToHost[ fd ] = h
    # Prepare to poll output files
    readable = poll()
    for t in tails.values():
        readable.register( t.stdout.fileno(), POLLIN )
    # Run until a set number of seconds have elapsed
    endTime = time() + seconds
    while time() < endTime:
        fdlist = readable.poll(timeoutms)
        if fdlist:
            for fd, _flags in fdlist:
                f = fdToFile[ fd ]
                host = fdToHost[ fd ]
                # Wait for a line of output
                line = f.readline().strip()
                yield host, line
        else:
            # If we timed out, return nothing
            yield None, ''
    for t in tails.values():
        t.terminate()
    devnull.close()  # Not really necessary


def monitorTest( N=3, seconds=3 ):
    "Run pings and monitor multiple hosts"
    topo = SingleSwitchTopo( N )
    net = Mininet( topo )
    net.start()
    hosts = net.hosts
    info( "Starting test...\n" )
    server = hosts[ 0 ]
    outfiles, errfiles = {}, {}
    for h in hosts:
        # Create and/or erase output files
        outfiles[ h ] = '/tmp/%s.out' % h.name
        errfiles[ h ] = '/tmp/%s.err' % h.name
        h.cmd( 'echo >', outfiles[ h ] )
        h.cmd( 'echo >', errfiles[ h ] )
        # Start pings
        h.cmdPrint('ping', server.IP(),
                   '>', outfiles[ h ],
                   '2>', errfiles[ h ],
                   '&' )
    info( "Monitoring output for", seconds, "seconds\n" )
    for h, line in monitorFiles( outfiles, seconds, timeoutms=500 ):
        if h:
            info( '%s: %s\n' % ( h.name, line ) )
    for h in hosts:
        h.cmd('kill %ping')
    net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    monitorTest()
