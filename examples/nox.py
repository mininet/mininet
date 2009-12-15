#!/usr/bin/python

"Instantiate a Tree network and use NOX as the controller."

from mininet.mininet import init, Controller, TreeNet, Cli

class NoxController( Controller ):
   def __init__( self, name, **kwargs ):
      Controller.__init__( self, name, 
         controller='nox_core',
         cargs='--libdir=/usr/local/lib -i ptcp: pyswitch', 
         cdir='/usr/local/bin', **kwargs)
   
if __name__ == '__main__':
   init()   
   network = TreeNet( depth=2, fanout=4, kernel=True, Controller=NoxController )
   network.run( Cli )
