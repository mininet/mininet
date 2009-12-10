#!/usr/bin/python

from mininet import init, TreeNet, iperfTest

def bigTreePing64():
   """Create a tree network of depth 4 and fanout 2, and 
      test connectivity using pingTest."""

   results = {}
   
   print "*** Testing Mininet with kernel and user datapath"
   
   for datapath in [ 'kernel', 'user' ]:
      k = datapath == 'kernel'
      results[ datapath ] = []
      for switchCount in range( 1, 4 ):
         print "*** Creating Linear Network of size", switchCount
         network = TreeNet( depth=4, fanout=2, kernel=k )
         testResult = network.run( iperfTest )
         results[ datapath ] += testResult
         
   print "*** Test results:", results
      
if __name__ == '__main__':
   init()
   linearBandwidthTest()

