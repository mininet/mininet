#!/usr/bin/python

"Run multiple tests on a network."
   
from mininet.mininet import init, TreeNet, pingTestVerbose, iperfTest, Cli

if __name__ == '__main__':
   init()
   network = TreeNet( depth=2, fanout=2, kernel=True )
   network.start()
   network.runTest( pingTestVerbose )
   network.runTest( iperfTest)
   network.runTest( Cli )
   network.stop()
