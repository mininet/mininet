#!/usr/bin/python

"""
Create a network where different switches are connected to
different controllers, by creating a custom Switch() subclass.
"""

from mininet.net import Mininet
from mininet.node import OVSSwitch, Controller
from mininet.topolib import TreeTopo
from mininet.cli import CLI

c0 = Controller( 'c0' )
c1 = Controller( 'c1', ip='127.0.0.2' )
cmap = { 's1': c0, 's2': c1, 's3': c1 }

class MultiSwitch( OVSSwitch ):
    "Custom Switch() subclass that connects to different controllers"
    def start( self, controllers ):
        return OVSSwitch.start( self, [ cmap[ self.name ] ] )

topo = TreeTopo( depth=2, fanout=2 )
net = Mininet( topo=topo, switch=MultiSwitch, build=False )
net.controllers = [ c0, c1 ]
net.build()
net.start()
CLI( net )
net.stop()
