#!/usr/bin/python

"Instantiate a Grid network and use NOX as the controller."

from mininet.mininet import init, Controller, GridNet, Cli

class NoxController( Controller ):
   def __init__( self, name, **kwargs ):
      Controller.__init__( self, name, 
         controller='nox_core', 
         cargs='-v --libdir=/usr/local/lib -i ptcp: routing', 
         cdir='/usr/local/bin', **kwargs)
   
if __name__ == '__main__':
   init()   
   network = GridNet( 2, 2, kernel=True, Controller=NoxController )
   network.run( Cli )
