#!/usr/bin/python

"""
Create a tree network and run udpbwtest.c on it, attempting to
saturate global bandwidth by sending constant all-to-all
udp traffic. This should be something of a stress test.

We should also make a tcp version. :D
"""

import os
import re
import select
import sys
import time

flush = sys.stdout.flush

from mininet.log import lg   
from mininet.net import init, Mininet
from mininet.node import Host, KernelSwitch
from mininet.topo import Topo, Node
from mininet.util import quietRun

class TreeTopo( Topo ):
    "Topology for a tree network with a given depth and fanout."

    def __init__( self, depth=1, fanout=2 ):
        super( TreeTopo, self ).__init__()
        # Build topology
        self.treeNet( 1, depth, fanout )
        # Consider all switches and hosts 'on'
        self.enable_all()

    def treeNet( self, id, depth, fanout ):
        """Add a subtree with a given id.
           returns: last id added"""
        me = id
        isSwitch = (depth > 0 )
        self._add_node( me, Node( is_switch=isSwitch ) )
        if isSwitch:
            for i in range( 0, fanout ):
                child = id + 1
                self._add_edge( me, child )
                id = self.treeNet( child, depth-1, fanout )
        return id

# Some useful stuff: buffered readline and host monitoring

def readline( host, buffer ):
   "Read a line from a host, buffering with buffer."
   buffer += host.read( 1024 )
   if '\n' not in buffer: return None, buffer
   pos = buffer.find( '\n' )
   line = buffer[ 0 : pos ]
   rest = buffer[ pos + 1 :]
   return line, rest

def monitor( hosts, seconds ):
   "Monitor a set of hosts and yield their output."
   poller = select.poll()
   Node = hosts[ 0 ] # so we can call class method
   buffers = {}
   for host in hosts:
      poller.register( host.stdout )
      buffers[ host ] = ''
   quitTime = time.time() + seconds
   while time.time() < quitTime:
      ready = poller.poll()
      for fd, event in ready: 
         host = Node.fdToNode( fd )
         line, buffers[ host ] = readline( host, buffers[ host ] )
         if line: yield host, line
   yield None, ''

# bwtest support

def parsebwtest( line,
   r=re.compile( r'(\d+) s: in ([\d\.]+) Mbps, out ([\d\.]+) Mbps' ) ):
   match = r.match( line )
   return match.group( 1, 2, 3 ) if match else ( None, None, None )
   
def printTotalHeader():
   print
   print "time(s)\thosts\ttotal in/out (Mbps)\tavg in/out (Mbps)"

def printTotal( time=None, result=None ):
   intotal = outtotal = 0.0
   count = len( result )
   for host, inbw, outbw in result:
      intotal += inbw
      outtotal += outbw
   inavg = intotal / count if count > 0 else 0
   outavg = outtotal / count if count > 0 else 0   
   print '%d\t%d\t%.2f/%.2f\t\t%.2f/%.2f' % ( time, count, intotal, outtotal,
      inavg, outavg )
   
def udpbwtest( net, seconds ):
   "Start up and monitor udpbwtest on each of our hosts."
   hosts, switches = net.hosts, net.switches
   hostCount = len( hosts )
   print "*** Starting udpbwtest on hosts"
   for host in hosts: 
      ips = [ h.IP() for h in hosts if h != host ]
      print host.name, ; flush()
      host.cmd( './udpbwtest ' + ' '.join( ips ) + ' &' )
   print
   results = {}
   print "*** Monitoring hosts"
   output = monitor( hosts, seconds )
   while True:
      host, line = output.next()
      if host is None: break
      time, inbw, outbw = parsebwtest( line )
      if time is not None:
         time, inbw, outbw = int( time ), float( inbw ), float( outbw )
         result = results.get( time, [] ) + [ ( host, inbw, outbw ) ]
         if len( result ) == hostCount: printTotal( time, result )
         results[ time ] = result
   print "*** Stopping udpbwtest processes"
   # We *really* don't want these things hanging around!
   quietRun( 'killall -9 udpbwtest' )
   print 
   print "*** Results:"
   printTotalHeader()
   times = sorted( results.keys() )
   for time in times:
      printTotal( time - times[ 0 ] , results[ time ] )
   print 
     
if __name__ == '__main__':
    lg.setLogLevel( 'info' )
    if not os.path.exists( './udpbwtest' ):
        raise Exception( 'Could not find udpbwtest in current directory.' )
    init()
    network = Mininet( TreeTopo( depth=2, fanout=2 ), switch=KernelSwitch )
    network.start()
    udpbwtest( network, seconds=10 )
    network.stop()
