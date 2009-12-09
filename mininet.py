#!/usr/bin/python

"""

Mininet: A simple networking testbed for OpenFlow!

Mininet creates a simple test network for OpenFlow by using
process-based virtualization and network namespaces. 

This file supports use of either the kernel or user space datapath
from the OpenFlow reference implementation. Up to 32 switches are
supported using the kernel datapath, and 512 (or more) switches are
supported via the user datapath.

Simulated hosts are created as processes in
separate network namespaces. This allows a complete OpenFlow
network to be simulated on top of a single Linux kernel.

Each host has:
   A virtual console (pipes to a shell)
   A virtual interfaces (half of a veth pair)
   A namespaced parent shell (and possibly some child processes)
   
Hosts have a network interface which is
configured via ifconfig/ip link/etc. with data network IP
addresses (e.g. 192.168.123.2 )

In kernel datapath mode, the controller and switches are simply
processes in the root namespace.

Kernel OpenFlow datapaths are instantiated using dpctl, and are
attached to the one side of a veth pair; the other side resides in
the host namespace. In this mode, switch processes can simply
connect to the controller via the loopback interface.

In user datapath mode, the controller and switch are full-service
nodes that live in their own network namespace and have management
interfaces and IP addresses on a control network (e.g. 10.0.123.1,
currently routed although it could be bridged.)

In addition to a management interface, user mode switches also have
several switch interfaces, halves of veth pairs whose other halves
reside in the host nodes that the switches are connected to.

Naming:
   Host nodes are named h1-hN
   Switch nodes are named s0-sN
   Interfaces are named {nodename}-eth0 .. {nodename}-ethN,

Thoughts/TBD:

   It should be straightforward to add a function to read
   OpenFlowVMS  spec files, but I haven't done so yet.
   For the moment, specifying configurations and tests in Python
   is straightforward and concise.
   Soon, we'll want to split the various subsystems (core,
   cli, tests, etc.) into multiple modules.
   We may be able to get better performance by using the kernel
   datapath (using its multiple datapath feature on multiple 
   interfaces.) This would eliminate the ofdatapath user processes.
   OpenVSwitch would still run at user level.
   
Bob Lantz
rlantz@cs.stanford.edu

History:
11/19/09 Initial revision (user datapath only)
12/8/08  Kernel datapath support complete

"""

# Note: this script must be run as root 
# Perhaps we should do so automatically!

from subprocess import call, check_call, Popen, PIPE, STDOUT
from time import sleep
import re, os, signal, sys, select
flush = sys.stdout.flush
from resource import setrlimit, RLIMIT_NPROC, RLIMIT_NOFILE

# Utility routines to make it easier to run commands

def run( cmd ):
   "Simple interface to subprocess.call()"
   return call( cmd.split( ' ' ) )

def checkRun( cmd ):
   "Simple interface to subprocess.check_call()"
   check_call( cmd.split( ' ' ) )
   
def quietRun( cmd ):
   "Run a command, routing stderr to stdout, and return the output."
   popen = Popen( cmd.split( ' '), stdout=PIPE, stderr=STDOUT)
   # We can't use Popen.communicate() because it uses 
   # select(), which can't handle
   # high file descriptor numbers! poll() can, however.
   output = ''
   readable = select.poll()
   readable.register( popen.stdout )
   while True:
      while readable.poll(): 
         data = popen.stdout.read( 1024 )
         if len( data ) == 0: break
         output += data
      popen.poll()
      if popen.returncode != None: break
   return output
   
# Command paths
netns = "/usr/local/bin/netns"
bash = "/bin/bash"
ifconfig = "/sbin/ifconfig"

class Node( object ):
   """A virtual network node is simply a shell in a network namespace.
      We communicate with it using pipes."""
   def __init__( self, name, inNamespace=True ):
      self.name = name
      closeFds = False # speed vs. memory use
      # xpg_echo is needed so we can echo our sentinel in sendCmd
      cmd = [ bash, '-O', 'xpg_echo' ]
      self.inNamespace = inNamespace
      if self.inNamespace: cmd = [ netns ] + cmd
      self.shell = Popen( cmd, stdin=PIPE, stdout=PIPE, stderr=STDOUT,
         close_fds=closeFds )
      self.stdin = self.shell.stdin
      self.stdout = self.shell.stdout
      self.pollOut = select.poll() 
      self.pollOut.register( self.stdout )
      outToNode[ self.stdout ] = self
      inToNode[ self.stdin ] = self
      self.pid = self.shell.pid
      self.intfCount = 0
      self.intfs = []
      self.ips = {}
      self.connection = {}
      self.waiting = False
      # For sanity check, try bringing up loopback interface
      # self.cmd( "ifconfig lo 127.0.0.1 up" )
   def read( self, max ): return os.read( self.stdout.fileno(), max )
   def write( self, data ): os.write( self.stdin.fileno(), data )
   def terminate( self ): os.kill( self.pid, signal.SIGKILL )
   def waitReadable( self ): self.pollOut.poll()
   def sendCmd( self, cmd ):
      """Send a command, followed by a command to echo a sentinel,
         and return without waiting for the command to complete."""
      assert not self.waiting
      if cmd[ -1 ] == '&':
         separator = '&'
         cmd = cmd[ : -1 ]
      else: separator = ';'
      if isinstance( cmd, list): cmd = ' '.join( cmd )
      self.write( cmd + separator + " echo -n '\\0177' \n")
      self.waiting = True
   def monitor( self ):
      "Monitor a command's output, returning (done, data)."
      assert self.waiting
      self.waitReadable()
      data = self.read( 1024 )
      if len( data ) > 0 and data[ -1 ] == chr( 0177 ):
         self.waiting = False
         return True, data[ : -1 ]
      else:
         return False, data
   def sendInt( self ):
      "Send ^C, hopefully interrupting a running subprocess."
      self.write( chr( 3 ) )
   def waitOutput( self ):
      """Wait for a command to complete (signaled by a sentinel
      character, ASCII(127) appearing in the output stream) and return
      the output, including trailing newline."""
      assert self.waiting
      output = ""
      while True:
         self.waitReadable()
         data = self.read( 1024 )
         if len(data) > 0  and data[ -1 ] == chr( 0177 ): 
            output += data[ : -1 ]
            break
         else: output += data
      self.waiting = False
      return output
   def cmd( self, cmd ):
      "Send a command, wait for output, and return it."
      self.sendCmd( cmd )
      return self.waitOutput()
   def cmdPrint( self, cmd ):
      "Call cmd, printing the command and output"
      print "***", self.name, ":", cmd
      result = self.cmd( cmd )
      print result,
      return result
   def intfName( self, n):
      "Construct a canonical interface name node-intf for interface N."
      return self.name + '-eth' + `n`
   def newIntf( self ):
      "Reserve and return a new interface name for this node."
      intfName = self.intfName( self.intfCount)
      self.intfCount += 1
      self.intfs += [ intfName ]
      return intfName
   def setIP( self, intf, ip, bits ):
      "Set an interface's IP address."
      result = self.cmd( [ ifconfig, intf, ip + bits, 'up' ] )
      self.ips[ intf ] = ip
      return result
   def setHostRoute( self, ip, intf ):
      "Add a route to the given IP address via intf."
      return self.cmd( 'route add -host ' + ip + ' dev ' + intf )
   def setDefaultRoute( self, intf ):
      "Set the default route to go through intf."
      self.cmd( 'ip route flush' )
      return self.cmd( 'route add default ' + intf )
   def IP( self ):
      "Return IP address of first interface"
      return self.ips[ self.intfs[ 0 ] ]    
   def __str__( self ): 
      result = self.name
      result += ": IP=" + self.IP() + " intfs=" + self.intfs
      result += " waiting=", self.waiting
      return result
 
# Maintain mapping between i/o pipes and nodes
# This could be useful for monitoring multiple nodes
# using select.poll()

inToNode = {}
outToNode = {}
def outputs(): return outToNode.keys()
def nodes(): return outToNode.values()
def inputs(): return [ node.stdin for node in nodes() ]
def nodeFromFile( f ):
   node = outToNode.get( f )
   return node or inToNode.get( f )

def createNodes( name, count ):
   "Create and return a list of nodes."
   nodes = [ Node( name + `i` ) for i in range( 0, count ) ]
   # print "*** CreateNodes: created:", nodes
   return nodes

# Interface management
# 
# We connect nodes by creating a pair of veth interfaces,
# and then placing them in the pair of nodes that we want
# to communicate. Interfaces are named nodeN-ethM

def makeIntfPair( intf1, intf2 ):
   "Make a veth pair of intf1 and intf2"
   # Delete any old interfaces with the same names
   quietRun( 'ip link del ' + intf1 )
   quietRun( 'ip link del ' + intf2 )
   # Create new pair
   cmd = 'ip link add name ' + intf1 + ' type veth peer name ' + intf2
   return checkRun( cmd )
   
def moveIntf( intf, node ):
   "Move intf to node"
   cmd = 'ip link set ' + intf + ' netns ' + `node.pid`
   checkRun( cmd )
   links = node.cmd( 'ip link show' )
   if not intf in links:
      print "*** Error: moveIntf:", intf, "not successfully moved to",
      print node.name,":"
      exit( 1 )
   return
   
def createLink( node1, node2 ):
   "Create a link node1-intf1 <---> node2-intf2."
   intf1 = node1.newIntf()
   intf2 = node2.newIntf()
   makeIntfPair( intf1, intf2 )
   if node1.inNamespace: moveIntf( intf1, node1 )
   if node2.inNamespace: moveIntf( intf2, node2 )
   node1.connection[ intf1 ] = ( node2, intf2 )
   node2.connection[ intf2 ] = ( node1, intf1 )
   return intf1, intf2

# Handy utilities

def parsePing( pingOutput ):
   "Parse ping output and return packets sent, received"
   r = r'(\d+) packets transmitted, (\d+) received'
   m = re.search( r, pingOutput )
   if m == None:
      print "*** Error: could not parse ping output:", pingOutput
      exit( 1 )
   sent, received  = int( m.group( 1 ) ), int( m.group( 2 ) )
   return sent, received

def pingTest( hosts, verbose=False ):
   "Test that each host can reach every other host."
   packets = 0 ; lost = 0
   for node in hosts:
      if verbose: 
         print node.name, "->", ; flush()
      for dest in hosts: 
         if node != dest:
            result = node.cmd( 'ping -c1 ' + dest.IP() )
            sent, received = parsePing( result )
            packets += sent
            if received > sent:
               print "*** Error: received too many packets"
               print result
               node.cmdPrint( 'route' )
               exit( 1 )
            lost += sent - received
            if verbose: 
               print ( dest.name if received else "X" ), ; flush()
      if verbose: print
   ploss = 100 * lost/packets
   if verbose:
      print "%d%% packet loss (%d/%d lost)" % ( ploss, lost, packets )
      flush()
   return ploss
   
def dumpNodes( nodes ):
   "Dump ifconfig of each node."
   for node in nodes:
      print "*** Dumping node", node.name
      print node.cmd( 'ip link show' )
      print node.cmd( 'route' )

def ipGen( A, B, c, d ):
   "Generate next IP class B IP address, starting at A.B.c.d"
   while True:
      yield '%d.%d.%d.%d' % ( A, B, c, d )
      d += 1
      if d > 254:
         d = 1
         c += 1
         if c > 254: break

def nameGen( prefix ):
   "Generate names starting with prefix."
   i = 0
   while True: 
      yield prefix + `i`
      i += 1

# Control network support
# Instead of routing, we could bridge or use "in-band" control

def checkUp( node ):
   "Make sure node's first interface is up."
   return 'UP' in node.cmd( 'ifconfig ' + node.intfs[ 0 ] )
   
def configRoutedControlNetwork( controller, switches ):
   "Configure a routed control network on controller and switches."
   cip = '10.0.0.1'
   sips = ipGen( 10, 123, 0, 1)
   print controller.name, '<->',
   for switch in switches:
      print switch.name, ; flush()
      sip = sips.next()
      sintf = switch.intfs[ 0 ]
      node, cintf = switch.connection[ sintf ]
      assert node == controller
      controller.setIP( cintf, cip,  '/24')
      switch.setIP( sintf, sip, '/24' )
      controller.setHostRoute( sip, cintf )
      switch.setHostRoute( cip, sintf )
   print
   print "*** Testing control network"
   while not checkUp( controller ):
      print "*** Waiting for ", controller.intfs[ 0 ], "to come up"
      sleep( 1 )
   for switch in switches:
      while not checkUp( switch ):
         print "*** Waiting for ", controller.intfs[ 0 ], "to come up"
         sleep( 1 )
      if pingTest( [ switch, controller ] ) != 0:
         print "*** Error: control network test failed"
      else:
         return
      exit( 1 )

def configHosts( hosts, ( a, b, c, d ) ):
   "Configure a set of hosts, starting at IP address a.b.c.d"
   ips = ipGen( a, b, c, d )
   for host in hosts:
      hintf = host.intfs[ 0 ]
      host.setIP( hintf, ips.next(), '/24' )
      host.setDefaultRoute( hintf )
      # You're low priority, dude!
      quietRun( 'renice +18 -p ' + `host.pid` )
      print host.name, ; flush()
   print

def startController( controller, cprog='controller', cargs='ptcp:' ):
   "Start <cprog cargs> on controller, logging to /tmp/cN.log"
   cout = '/tmp/' + controller.name + '.log'
   controller.cmdPrint( cprog + ' ' + cargs + 
      ' 1> ' + cout + ' 2> ' + cout + ' &' )

def stopController( controller, cprog='controller' ):
   "Stop controller cprog on controller"
   controller.cmd( "kill %" + cprog )
   
def startOpenFlowU( switch, controller ):
   """Start OpenFlow reference user datapath on a switch, 
      logging to /tmp/sN-{ofd,ofp}.log"""
   ofdlog = '/tmp/' + switch.name + '-ofd.log'
   ofplog = '/tmp/' + switch.name + '-ofp.log'
   switch.cmd( 'ifconfig lo up' )
   intfs = switch.intfs[ 1 : ] # 0 is mgmt interface
   switch.cmdPrint( 'ofdatapath -i ' + ','.join( intfs ) +
    ' ptcp: 1> ' + ofdlog + ' 2> '+ ofdlog + ' &' )
   switch.cmdPrint( 'ofprotocol tcp:' + controller.IP() +
      ' tcp:localhost 1> ' + ofplog + ' 2>' + ofplog + '&' )

def stopOpenFlowU( switch ):
   "Stop OpenFlow reference user datapath on a switch."
   switch.cmd( "kill %ofdatapath" )
   switch.cmd( "kill %ofprotocol" )   

def dpgen():
   "Generator for OpenFlow kernel datapath names."
   dpCount = 0
   while True:
      yield 'nl:' + `dpCount`
      dpCount += 1

def startOpenFlowK( switch, dp, controller):
   "Start up a switch connected to an OpenFlow reference kernel datapath."
   ofplog = '/tmp/' + switch.name + '-ofp.log'
   switch.cmd( 'ifconfig lo up' )
   # Delete local datapath if it exists;
   # then create a new one monitoring the given interfaces
   quietRun( 'dpctl deldp ' + dp )
   switch.cmdPrint( 'dpctl adddp ' + dp )
   switch.cmdPrint( 'dpctl addif ' + dp + ' ' + ' '.join( switch.intfs ) )
   switch.dp = dp
   # Become protocol daemon
   switch.cmdPrint( 'exec ofprotocol' +
      ' ' + dp + ' tcp:127.0.0.1 1> ' + ofplog + ' 2>' + ofplog + '&' )

def stopOpenFlowK( switch ):
   "Terminate a switch using OpenFlow reference kernel datapath."
   quietRun( 'dpctl deldp ' + switch.dp )
   for intf in switch.intfs: quietRun( 'ip link del ' + intf )
   switch.terminate()

def stopOpenFlow( switch ):
   if hasattr(switch, 'dp' ): stopOpenFlowK( switch )
   else: stopOpenFlowU( switch )

# Test scenarios and topologies

def treeNet( controller, depth, fanout, snames=nameGen( 's' ), 
   hnames=nameGen( 'h' ), kernel=True ):
   """Return a tree network of the given depth and fanout as a triple:
      ( root, switches, hosts ), using the given switch and host
      name generators, with the switches connected to the given
      controller."""
   if ( depth == 0 ):
      host = Node( hnames.next() )
      print host.name, ; flush()
      return host, [], [ host ]
   switch = Node( snames.next(), inNamespace=(not kernel) )
   if not kernel: createLink( switch, controller )
   print switch.name, ; flush()
   switches, hosts = [ switch ], []
   for i in range( 0, fanout ):
      child, slist, hlist = treeNet( 
         controller, depth - 1, fanout, snames, hnames, kernel )
      createLink( switch, child )
      switches += slist
      hosts += hlist
   return switch, switches, hosts

def treeNetTest( depth, fanout, test, kernel=True ):
   """Create a tree network of the given depth and fanout, and
      run test( controller, root, switches, hosts ) on it."""
   if kernel: print "*** Using kernel datapath"
   else: print "*** Using user datapath"
   print "*** Creating controller"
   controller = Node( 'c0', inNamespace=( not kernel ) )
   print "*** Creating tree network depth:", depth, "fanout:", fanout
   root, switches, hosts = treeNet( controller, depth, fanout, kernel=kernel )
   print
   if not kernel:
      print "*** Configuring control network"
      configRoutedControlNetwork( controller, switches )
   else: dp = dpgen()
   print "*** Configuring hosts"
   configHosts( hosts, ( 192, 168, 123, 1 ) )
   print "*** Starting reference controller"
   startController( controller )
   print "*** Starting switches"
   for switch in switches:
      if kernel: startOpenFlowK( switch, dp.next(), controller )
      else: startOpenFlowU( switch, controller )
   print "*** Running test"
   test( controller, root, switches, hosts )
   print "*** Stopping controller"
   stopController( controller )
   print "*** Stopping switches"
   for switch in switches:
      stopOpenFlow( switch )

def treePingTest( depth, fanout, kernel=True ):
   "Run a ping test on a tree network with the given depth and fanout."
   test = lambda c, r, s, hosts : pingTest( hosts, verbose=True )
   treeNetTest( depth, fanout, test, kernel)
   
def iperf( hosts ):
   "Run iperf between two hosts."
   assert len( hosts ) == 2
   host1, host2 = hosts[ 0 ], hosts[ 1 ]
   dumpNodes( [ host1, host2 ] )
   host1.cmdPrint( 'killall -9 iperf')
   host1.cmdPrint( 'iperf -s &' )
   host2.cmdPrint( 'iperf -t 5 -c ' + host1.IP() )
   host1.cmdPrint( 'kill -9 %iperf' )
 
def iperfTest( depth=1, fanout=2, kernel=True ):
   "Simple iperf test between two hosts."
   def test( c, r, s, hosts ):
      h0, hN = hosts[ 0 ], hosts[ -1 ]
      print "*** iperfTest: Testing bandwidth between", 
      print h0.name, "and", hN.name
      return iperf( [ h0, hN] )
   treeNetTest( depth, fanout, test, kernel )
   
def fixLimits():
   "Fix ridiculously small resource limits."
   setrlimit( RLIMIT_NPROC, ( 4096, 8192 ) )
   setrlimit( RLIMIT_NOFILE, ( 16384, 32768 ) )

# Simple CLI

def cliHelp( nodemap, c, s, h, args  ):
   "Semi-useful help for CLI"
   print "available commands are:", cliCmds.keys()

def cliNodes( nodemap, c, s, h, args ):
   "List available nodes"
   print "available nodes are:", nodemap.keys()
      
def cliSh( nodemap, c, s, h, args ):
   "Run an external shell command"
   call( [ bash, '-c', args ] )

def cliPingTest( map, c, s, hosts, args ):
   pingTest( hosts, verbose=True )

def cliNet( map, c, switches, h, args ):
   for switch in switches:
      print switch.name, "<->",
      for intf in switch.intfs:
         node, rintf = switch.connection[ intf ]
         print node.name,
      print

def cliIperf( map, c, switches, h, args ):
   print "iperf: got args", args
   if len( args ) != 2:
      print "usage: iperf <h1> <h2>"
      return
   for host in args:
      if host not in map:
         print "iperf: cannot find host:", host
         return
   iperf( [ map[ h ] for h in args ] )

cliCmds = { '?': cliHelp, 'help': cliHelp, 'net': cliNet, 'nodes': cliNodes, 
         'pingtest': cliPingTest, 'iperf': cliIperf, 'sh': cliSh, 
         'exit': None }

def cli( controllers, switches, hosts ):
   "Simple command-line interface to talk to nodes."
   print "*** cli: starting"
   nodemap = {}
   nodes = controllers + switches + hosts
   for node in nodes:
      nodemap[ node.name ] = node
   while True:
      print "mininet> ", ; flush()
      input = sys.stdin.readline()
      if input == '': break
      if input[ -1 ] == '\n': input = input[ : -1 ]
      cmd = input.split( ' ' )
      first = cmd[ 0 ]
      rest = cmd[ 1: ]
      if first in cliCmds: cliCmds[ first ]( 
         nodemap, controllers, switches, hosts, rest )
      elif first in nodemap and rest != []:
         node = nodemap[ first ]
         # Substitute IP addresses for node names in command
         rest = [ nodemap[ arg ].IP() if arg in nodemap else arg
            for arg in rest ]
         rest = ' '.join( rest )
         # Interactive commands don't work yet, and
         # there are still issues with control-c
         print "***", node.name, ": running", rest
         node.sendCmd( rest )
         while True:
            try:
               done, data = node.monitor()
               print data,
               if done: break
            except KeyboardInterrupt: node.sendInt()
         print
      elif first == '': pass
      elif first in [ 'exit', 'quit' ]: break
      else: print "cli: unknown node or command: <", first, ">"
   print "*** cli: exiting"
      
def treeInteract( depth, fanout, kernel=True ):
   "Create a tree network and start the CLI."
   interact = lambda c, r, s, h : cli( [ c ], s, h )
   treeNetTest( depth, fanout, interact, kernel )
   
if __name__ == '__main__':
   fixLimits()
   # for kernel in [ False, True ]:
   #   treePingTest( depth=3, fanout=4, kernel=kernel )
   # treeInteract( depth=1, fanout=2, kernel=False )
   #  iperfTest( depth=1, fanout=2, kernel=kernel )
   treeInteract( depth=1, fanout=2, kernel=False )