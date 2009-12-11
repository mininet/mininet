#!/usr/bin/python

"Create a 64-node tree network, and test connectivity using ping."
   
from mininet import init, TreeNet, pingTestVerbose

def treePing64():
   results = {}
   datapaths = [ 'kernel', 'user' ]
   
   print "*** Testing Mininet with kernel and user datapaths"
   
   for datapath in datapaths:
      k = datapath == 'kernel'
      network = TreeNet( depth=2, fanout=8, kernel=k )
      result = network.run( pingTestVerbose )
      results[ datapath ] = result
   
   print  
   print "*** TreeNet ping results:"
   for datapath in datapaths:
      print "%s:" % datapath, results[ datapath ]
   print
   
if __name__ == '__main__':
   init()
   treePing64()

