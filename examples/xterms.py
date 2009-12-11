#!/usr/bin/python

"""
Create a network and run an xterm (connected via screen(1) ) on each
host. Requires xterm(1) and GNU screen(1).
"""

import os, re
from subprocess import Popen
from mininet import init, TreeNet, Cli, quietRun

def makeXterm( node, title ):
   "Run screen on a node, and hook up an xterm."
   node.cmdPrint( 'screen -dmS ' + node.name )
   title += ': ' + node.name
   if not node.inNamespace: title += ' (root)'
   cmd = [ 'xterm', '-title', title ]
   cmd += [ '-e', 'screen', '-D', '-RR', '-S', node.name ]
   return Popen( cmd )

def cleanUpScreens():
   "Remove moldy old screen sessions."      
   r = r'(\d+.[hsc]\d+)'
   output = quietRun( 'screen -ls' ).split( '\n' )
   for line in output:
      m = re.search( r, line )
      if m is not None:
         quietRun( 'screen -S ' + m.group( 1 ) + ' -X kill' )
   
def makeXterms( nodes, title ):
   terms = []
   for node in nodes:
      if not node.execed:
         terms += [ makeXterm( node, title ) ]
   return terms

def xterms( controllers, switches, hosts ):
   cleanUpScreens()
   terms = []
   terms += makeXterms( controllers, 'controller' )
   terms += makeXterms( switches, 'switch' )
   terms += makeXterms( hosts, 'host' )
   # Wait for xterms to exit
   for term in terms: 
      os.waitpid( term.pid, 0 )
   cleanUpScreens()
   
if __name__ == '__main__':
   init()
   print "Running xterms on", os.environ[ 'DISPLAY' ]
   network = TreeNet( depth=2, fanout=2, kernel=True )
   network.run( xterms )
