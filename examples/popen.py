#!/usr/bin/python

"""
This example tests the Host.popen()/pexec() interface
"""

from mininet.net import Mininet
from mininet.node import CPULimitedHost
from mininet.topo import SingleSwitchTopo
from mininet.log import setLogLevel
# from mininet.cli import CLI
from mininet.util import custom

def testpopen(sched='cfs'):
    "Test popen() interface"
    host = custom( CPULimitedHost, cpu=.2, sched=sched )
    net = Mininet( SingleSwitchTopo( 2 ), host=host )
    net.start()
    h1 = net.get( 'h1' )
    # CLI(net)
    out, err, code = h1.pexec( 'ifconfig' )
    print 'stdout:', out.strip()
    print 'stderr:', err.strip()
    print 'exit code:', code
    net.stop()

if __name__ == '__main__':
    setLogLevel( 'info' )
    testpopen('rt')
    testpopen('cfs')
