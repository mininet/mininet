#!/usr/bin/python

"A FatTree network, using Brandon Heller's ripcord system."

from ripcord.topo import StructuredNode, StructuredNodeSpec, FatTreeTopo, VL2T
opo

from mininet import Controller, Network, Host, pingTest

class NoxController( Controller ):
   "A customized Controller that uses NOX."
   def __init__( self, name, **kwargs ):
      Controller.__init__( self, name, 
         controller='nox_core', cargs='-i ptcp pyswitch', 
         cdir='/usr/local/bin', **kwargs)
   
class FatTree( Network ):
   "A customized Network that uses ripcord's FatTree."
   def __init__( self, **kwargs ):
      Network.__init__( self, depth, **kwargs )
   def makeNetwork( self, controller ):
      ft = FatTreeTopo( depth )
      graph = ft.g
      switches = []
      hosts = []
      hostnames = nameGen( 'h0' )
      switchnames = nameGen( 's0' )
      graphToMini = {}
      miniToGraph = {}
      # Create nodes
      for graphNode in graph.nodes():
         print "found node", graphNode
         isLeaf = len( graph.neighbors( graphNode ) ) = 1
         if isLeaf:
            mininetNode = Node( hostnames.next() )
            hosts += [ mininetNode ]
         else:
            mininetNode = self.Switch( switchnames.next() )
            switches += [ mininetNode ]
            miniToGraph[ mininetNode ] = graphNode
            graphToMini[ graphNode ] = mininetNode
      # Create Links
      for switch in switches:
         for neighbor in miniToGraph[ switches ]:
            makeLink( switch, graphToMini[ neighbor ] )

if __name__ == '__main__':
   init()   
   network = FatTree( depth=4, kernel=True, Controller=NoxController)
   network.run( pingTest )
