#!/usr/bin/python

from mininet import init, LinearNet, iperfTest

def linearBandwidthTest():
   """Test bandwidth on a linear network of varying size, using both
      the kernel and user datapaths."""
  
   print "*** Testing Mininet with kernel and user datapath"
   
   datapaths = [ 'kernel' ]
   results = {}
      
   for datapath in datapaths:
      k = datapath == 'kernel'
      results[ datapath ] = []
      for switchCount in range( 1, 17, 2 ):
         print "*** Creating Linear Network of size", switchCount
         network = LinearNet( switchCount, k)
         bandwidth = network.run( iperfTest )
         results[ datapath ] += [ ( switchCount, bandwidth ) ]
         
   for datapath in datapaths:
      print
      print "*** Linear network results for", datapath, "datapath"
      print
      result = results[ datapath ]  
      for switchCount, bandwidth in result:
         print "switchCount:", switchCount, "bandwidth:", bandwidth[ 0 ]
       
if __name__ == '__main__':
   init()
   linearBandwidthTest()
   exit( 1 )

   