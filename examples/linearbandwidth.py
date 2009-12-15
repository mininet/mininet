#!/usr/bin/python

"""
Test bandwidth (using iperf) on linear networks of varying size, 
using both kernel and user datapaths.

Each network has N switches and N+1 hosts, connected as follows:

h0 <-> s0 <-> s1 .. sN-1
        |      |     |
        h1     h2    hN
        
Note: by default, the reference controller only supports 16
switches, so this test WILL NOT WORK unless you have recompiled
your controller to support 100 switches (or more.)
"""
   
from mininet.mininet import init, Network, defaultNames, Host, Switch
from mininet.mininet import createLink, flush, iperf, pingTestVerbose, Cli

class LinearNet( Network ):
   def __init__( self, switchCount, **kwargs ):
      self.switchCount = switchCount
      Network.__init__( self, **kwargs )
   def makeNet( self, controller ):
      snames, hnames, dpnames = defaultNames()
      previous = None
      hosts = []
      switches = []
      def newHost( switch ):
         host = Host( hnames.next() )
         createLink( host, switch )
         print host.name, ; flush()
         return [ host ]
      print "*** Creating linear network of size", self.switchCount
      for s in range( 0, self.switchCount ):
         dp = dpnames.next() if self.kernel else None
         switch = Switch( snames.next(), dp )
         switches += [ switch ]
         print switch.name, ; flush()
         if not self.kernel: createLink( controller, switch )
         if s == 0: hosts += newHost( switch )
         hosts += newHost( switch)
         if previous is not None: createLink( previous, switch)
         previous = switch
      return switches, hosts
   
def linearBandwidthTest( lengths ):

   "Check bandwidth at various lengths along a switch chain."
   
   datapaths = [ 'kernel', 'user' ]
   results = {}
   switchCount = max( lengths )
   
   for datapath in datapaths:
      k = datapath == 'kernel'
      results[ datapath ] = []
      network = LinearNet( switchCount, kernel=k)
      network.start()
      for n in lengths:
         def test( controllers, switches, hosts ):
            print "testing h0 <-> h" + `n`, ; flush()
            result = iperf( [ hosts[ 0 ], hosts[ n ] ] )
            print result ; flush()
            return result
         bandwidth = network.runTest( test )
         results[ datapath ] += [ ( n, bandwidth ) ]
      network.stop()
      
   for datapath in datapaths:
      print
      print "*** Linear network results for", datapath, "datapath:"
      print
      result = results[ datapath ]  
      print "SwitchCount\tiperf Results"
      for switchCount, bandwidth in result:
         print switchCount, '\t\t', 
         print bandwidth[ 0 ], 'server, ', bandwidth[ 1 ], 'client'
      print
   print
      
if __name__ == '__main__':
   init()
   print "*** Running linearBandwidthTest"
   linearBandwidthTest( [ 1, 10, 20, 40, 60, 80, 100 ] )

   
