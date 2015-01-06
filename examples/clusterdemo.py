#!/usr/bin/python

"clusterdemo.py: demo of Mininet Cluster Edition prototype"

from mininet.examples.cluster import MininetCluster, SwitchBinPlacer
from mininet.topolib import TreeTopo
from mininet.log import setLogLevel
from mininet.examples.clustercli import ClusterCLI as CLI

def demo():
    "Simple Demo of Cluster Mode"
    servers = [ 'localhost', 'ubuntu2', 'ubuntu3' ]
    topo = TreeTopo( depth=3, fanout=3 )
    net = MininetCluster( topo=topo, servers=servers,
                          placement=SwitchBinPlacer )
    net.start()
    CLI( net )
    net.stop()

if __name__ == '__main__':
    setLogLevel( 'info' )
    demo()
