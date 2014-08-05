#!/usr/bin/python

"Create a k = 4 fattree network and run CLI"

from functools import partial
from mininet.log import setLogLevel
from mininet.node import RiplPOX
from mininet.topolib import FatTreeNet
from mininet.cli import CLI

def fatTree():
    "Open CLI on k = 4 fattree network with RiplPOX controller running in background"
    k = 4 
    fanout = 2
    speed = 1.0
    controller = partial( RiplPOX, cargs='--no-cli openflow.of_01 --port=%s riplpox.riplpox ' +
                                        '--topo=fattree,' + str(k) + ',' + str(fanout) +
                                        ' --routing=random --mode=reactive')
    network = FatTreeNet( k=k, fanout=fanout, speed=speed, controller=controller )
    network.run( CLI, network )

if __name__ == '__main__':
    setLogLevel( 'info' )
    fatTree()
