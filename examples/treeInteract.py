#!/usr/bin/python

"Create a tree network and run the CLI on it."

from mininet import init, TreeNet, Cli

if __name__ == '__main__':
   init()
   network = TreeNet( depth=2, fanout=4, kernel=True )
   network.run( Cli )
