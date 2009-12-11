#!/usr/bin/python

"""Create a tree network of depth 4 and fanout 2, and 
   test connectivity using pingTest."""
   
from mininet import init, TreeNet, pingTestVerbose

def bigTreePing64():
   results = {}

   print "*** Testing Mininet with kernel and user datapath"
   
   for datapath in [ 'kernel', 'user' ]:
      k = datapath == 'kernel'
      results[ datapath ] = []
      for switchCount in range( 1, 4 ):
         network = TreeNet( depth=3, fanout=4, kernel=k )
         testResult = network.run( pingTestVerbose )
         results[ datapath ] += testResult
         
   print "*** Test results:", results
      
if __name__ == '__main__':
   init()
   bigTreePing64()

