#!/usr/bin/python

"""
Create a network and run an xterm (connected via screen(1) ) on each host.
Requires xterm(1) and GNU screen(1).
"""

import os
from subprocess import Popen
from mininet import init, TreeNet, Cli, quietRun

def makeXterm( node, title ):
   "Run screen on a node, and hook up an xterm."
   node.cmdPrint( 'screen -dmS ' + node.name )
   title += ': ' + node.name
   if not node.inNamespace:
      title += ' (root namespace)'
   cmd = [ 'xterm', '-title', title ]
   cmd += [ '-e', 'screen', '-D', '-RR', '-S', node.name ]
   return Popen( cmd )

def cleanUpScreens():
   "Remove moldy old screen sessions."      
   # XXX We need to implement this - otherwise those darned
   # screen sessions will just accumulate
   output = quietRun( 'screen -ls' )
   pass
   
def makeXterms( nodes, title ):
   terms = []
   for node in nodes:
      if not node.execed:
         terms += [ makeXterm( node, title ) ]
   return terms

def xterms( controllers, switches, hosts ):
   terms = []
   terms += makeXterms( controllers, 'controller' )
   terms += makeXterms( switches, 'switch' )
   terms += makeXterms( hosts, 'host' )
   # Wait for xterms to exit
   for term in terms:
      os.waitpid( term.pid, 0 )
   
if __name__ == '__main__':
   init()
   print "Running xterms on", os.environ[ 'DISPLAY' ]
   cleanUpScreens()
   network = TreeNet( depth=2, fanout=2, kernel=True )
   network.run( xterms )
   cleanUpScreens()