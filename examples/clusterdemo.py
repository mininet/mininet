#!/usr/bin/python

"clusterdemo.py: demo of Mininet Cluster Edition prototype"

from mininet.cluster.net import MininetCluster
from mininet.cluster.placer import SwitchBinPlacer
from mininet.topolib import TreeTopo
from mininet.log import setLogLevel
from mininet.cluster.cli import ClusterCLI as CLI

def demo():
    "Simple Demo of Cluster Mode"
    #servers = [ 'localhost', 'ubuntu2', 'ubuntu3' ]
    servers = [ 'master', 'opennetslave1' ]
    topo = TreeTopo( depth=3, fanout=3 )
    net = MininetCluster( topo=topo, servers=servers,
                          placement=SwitchBinPlacer )
    net.start()
    CLI( net )
    net.stop()

if __name__ == '__main__':
    setLogLevel( 'info' )
    demo()
