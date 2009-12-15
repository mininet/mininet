#!/usr/bin/python

"A FatTree network, using Brandon Heller's ripcord system."

import ripcord
from ripcord.topo import FatTreeTopo

from mininet import init, Controller, Network, Host, nameGen, Cli
from mininet import createLink, flush

class NoxController( Controller ):
   "A customized Controller that uses NOX."
   def __init__( self, name, **kwargs ):
      Controller.__init__( self, name, 
         controller='nox_core', cargs='-i ptcp pyswitch', 
         cdir='/usr/local/bin', **kwargs)
   
class FatTree( Network ):
   "A customized Network that uses ripcord's FatTree."
   def __init__( self, depth, **kwargs ):
      self.depth = depth
      Network.__init__( self, **kwargs )
   def makeNet( self, controller ):
      ft = FatTreeTopo( self.depth )
      graph = ft.g
      switches = []
      hosts = []
      hostnames = nameGen( 'h' )
      switchnames = nameGen( 's' )
      dpnames = nameGen( 'nl:')
      graphToMini = {}
      miniToGraph = {}
      # Create nodes
      for graphNode in graph.nodes():
         isLeaf = len( graph.neighbors( graphNode ) ) == 1
         if isLeaf:
            mininetNode = Host( hostnames.next() )
            hosts += [ mininetNode ]
         else:
            mininetNode = self.Switch( switchnames.next(), dpnames.next() )
            switches += [ mininetNode ]
         print mininetNode.name, ; flush()
         miniToGraph[ mininetNode ] = graphNode
         graphToMini[ graphNode ] = mininetNode
      print
      print "*** Creating links"
      for switch in switches:
         currentNeighbors = [ switch.connection[ intf ][ 0 ] 
            for intf in switch.intfs ]
         for neighbor in graph.neighbors( miniToGraph[ switch ] ):
            miniNeighbor = graphToMini[ neighbor ]
            if miniNeighbor not in currentNeighbors:
               print ".", ; flush()
               createLink( switch, graphToMini[ neighbor ] )
      print
      return switches, hosts
      
if __name__ == '__main__':
   init()   
   network = FatTree( depth=4, kernel=True, Controller=NoxController)
   network.run( Cli )
