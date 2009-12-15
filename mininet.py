#!/usr/bin/python

"""
Mininet: A simple networking testbed for OpenFlow!

Mininet creates scalable OpenFlow test networks by using
process-based virtualization and network namespaces. 

Simulated hosts are created as processes in separate network
namespaces. This allows a complete OpenFlow network to be simulated on
top of a single Linux kernel.

Each host has:
   A virtual console (pipes to a shell)
   A virtual interfaces (half of a veth pair)
   A parent shell (and possibly some child processes) in a namespace
   
Hosts have a network interface which is configured via ifconfig/ip
link/etc. with data network IP addresses (e.g. 192.168.123.2 )

This version supports both the kernel and user space datapaths
from the OpenFlow reference implementation.

In kernel datapath mode, the controller and switches are simply
processes in the root namespace.

Kernel OpenFlow datapaths are instantiated using dpctl(8), and are
attached to the one side of a veth pair; the other side resides in the
host namespace. In this mode, switch processes can simply connect to the
controller via the loopback interface.

In user datapath mode, the controller and switches are full-service
nodes that live in their own network namespaces and have management
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
   OpenFlowVMS spec files, but I haven't done so yet.
   For the moment, specifying configurations and tests in Python
   is straightforward and relatively concise.
   Soon, we may want to split the various subsystems (core,
   cli, tests, etc.) into multiple modules.
   We don't support nox nicely just yet - you have to hack this file
   or subclass things aggressively.
   We'd like to support OpenVSwitch as well as the reference
   implementation.
   
Bob Lantz
rlantz@cs.stanford.edu

History:
11/19/09 Initial revision (user datapath only)
11/19/09 Mininet demo at OpenFlow SWAI meeting
12/08/09 Kernel datapath support complete
12/09/09 Moved controller and switch routines into classes
12/12/09 Added subdivided network driver workflow
12/13/09 Added support for custom controller and switch classes
"""

from subprocess import call, check_call, Popen, PIPE, STDOUT
from time import sleep
import os, re, signal, sys, select
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
   if isinstance( cmd, str ): cmd = cmd.split( ' ' )
   popen = Popen( cmd, stdout=PIPE, stderr=STDOUT)
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
   
class Node( object ):
   """A virtual network node is simply a shell in a network namespace.
      We communicate with it using pipes."""
   def __init__( self, name, inNamespace=True ):
      self.name = name
      closeFds = False # speed vs. memory use
      # xpg_echo is needed so we can echo our sentinel in sendCmd
      cmd = [ '/bin/bash', '-O', 'xpg_echo' ]
      self.inNamespace = inNamespace
      if self.inNamespace: cmd = [ 'netns' ] + cmd
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
      self.execed = False
   def cleanup( self ):
      # Help python collect its garbage
      self.shell = None
   # Subshell I/O, commands and control
   def read( self, max ): return os.read( self.stdout.fileno(), max )
   def write( self, data ): os.write( self.stdin.fileno(), data )
   def terminate( self ):
      self.cleanup()
      os.kill( self.pid, signal.SIGKILL )
   def stop( self ): self.terminate()
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
   # Interface management, configuration, and routing
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
      result = self.cmd( [ 'ifconfig', intf, ip + bits, 'up' ] )
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
   def intfIsUp( self, intf ):
      "Check if one of our interfaces is up."
      return 'UP' in self.cmd( 'ifconfig ' + self.intfs[ 0 ] )
   # Other methods  
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

class Host( Node ):
   """A host is simply a Node."""
   pass
      
class Controller( Node ):
   """A Controller is a Node that is running (or has execed) an 
      OpenFlow controller."""
   def __init__( self, name, kernel=True, controller='controller',
      cargs='ptcp:', cdir=None ):
      self.controller = controller
      self.cargs = cargs
      self.cdir = cdir
      Node.__init__( self, name, inNamespace=( not kernel ) )
   def start( self ):
      "Start <controller> <args> on controller, logging to /tmp/cN.log"
      cout = '/tmp/' + self.name + '.log'
      if self.cdir is not None:
         self.cmdPrint( 'cd ' + self.cdir )
      self.cmdPrint( self.controller + ' ' + self.cargs + 
         ' 1> ' + cout + ' 2> ' + cout + ' &' )
      self.execed = False # XXX Until I fix it
   def stop( self, controller='controller' ):
      "Stop controller cprog on controller"
      self.cmd( "kill %" + controller )  
      self.terminate()
         
class Switch( Node ):
   """A Switch is a Node that is running (or has execed)
      an OpenFlow switch."""
   def __init__( self, name, datapath=None ):
      self.dp = datapath
      Node.__init__( self, name, inNamespace=( datapath == None ) )
   def startUserDatapath( self, controller ):
      """Start OpenFlow reference user datapath, 
         logging to /tmp/sN-{ofd,ofp}.log"""
      ofdlog = '/tmp/' + self.name + '-ofd.log'
      ofplog = '/tmp/' + self.name + '-ofp.log'
      self.cmd( 'ifconfig lo up' )
      intfs = self.intfs[ 1 : ] # 0 is mgmt interface
      self.cmdPrint( 'ofdatapath -i ' + ','.join( intfs ) +
       ' ptcp: 1> ' + ofdlog + ' 2> '+ ofdlog + ' &' )
      self.cmdPrint( 'ofprotocol tcp:' + controller.IP() +
         ' tcp:localhost 1> ' + ofplog + ' 2>' + ofplog + ' &' )
   def stopUserDatapath( self ):
      "Stop OpenFlow reference user datapath."
      self.cmd( "kill %ofdatapath" )
      self.cmd( "kill %ofprotocol" )
   def startKernelDatapath( self, controller):
      "Start up switch using OpenFlow reference kernel datapath."
      ofplog = '/tmp/' + self.name + '-ofp.log'
      quietRun( 'ifconfig lo up' )
      # Delete local datapath if it exists;
      # then create a new one monitoring the given interfaces
      quietRun( 'dpctl deldp ' + self.dp )
      self.cmdPrint( 'dpctl adddp ' + self.dp )
      self.cmdPrint( 'dpctl addif ' + self.dp + ' ' + ' '.join( self.intfs ) )
      # Become protocol daemon
      self.cmdPrint( 'ofprotocol' +
         ' ' + self.dp + ' tcp:127.0.0.1 1> ' + ofplog + ' 2>' + ofplog + ' &' )
      self.execed = False # XXX until I fix it
   def stopKernelDatapath( self ):
      "Terminate a switch using OpenFlow reference kernel datapath."
      quietRun( 'dpctl deldp ' + self.dp )
      # In theory the interfaces should go away after we shut down.
      # However, this takes time, so we're better off to remove them
      # explicitly so that we won't get errors if we run before they
      # have been removed by the kernel. Unfortunately this is very slow.
      for intf in self.intfs:
         quietRun( 'ip link del ' + intf )
         sys.stdout.write( '.' ) ; flush()
      self.cmd( 'kill %ofprotocol')
   def start( self, controller ): 
      if self.dp is None: self.startUserDatapath( controller )
      else: self.startKernelDatapath( controller )
   def stop( self ):
      if self.dp is None: self.stopUserDatapath()
      else: self.stopKernelDatapath()
      # Handle non-interaction if we've execed
      self.terminate()
   def sendCmd( self, cmd ):
      if not self.execed: return Node.sendCmd( self, cmd )
      else: print "*** Error:", self.name, "has execed and cannot accept commands"
   def monitor( self ):
      if not self.execed: return Node.monitor( self )
      else: return True, ''
         
# Interface management
# 
# Interfaces are managed as strings which are simply the
# interface names, of the form "nodeN-ethM".
#
# To connect nodes, we create a pair of veth interfaces, and then place them
# in the pair of nodes that we want to communicate. We then update the node's
# list of interfaces and connectivity map.
#
# For the kernel datapath, switch interfaces
# live in the root namespace and thus do not have to be
# explicitly moved.

def makeIntfPair( intf1, intf2 ):
   "Make a veth pair of intf1 and intf2."
   # Delete any old interfaces with the same names
   quietRun( 'ip link del ' + intf1 )
   quietRun( 'ip link del ' + intf2 )
   # Create new pair
   cmd = 'ip link add name ' + intf1 + ' type veth peer name ' + intf2
   return checkRun( cmd )
   
def moveIntf( intf, node ):
   "Move intf to node."
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
 
def createNodes( name, count ):
   "Create and return a list of nodes."
   nodes = [ Node( name + `i` ) for i in range( 0, count ) ]
   # print "*** CreateNodes: created:", nodes
   return nodes
     
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
   while True: yield prefix + `i`; i += 1
      
# Control network support
# For the user datapath, we create an explicit control network.
# Note: Instead of routing, we could bridge or use "in-band" control
   
def configureRoutedControlNetwork( controller, switches, ips):
   """Configure a routed control network on controller and switches,
      for use with the user datapath."""
   cip = ips.next()
   print controller.name, '<->',
   for switch in switches:
      print switch.name, ; flush()
      sip = ips.next()
      sintf = switch.intfs[ 0 ]
      node, cintf = switch.connection[ sintf ]
      if node != controller:
         print "*** Error: switch", switch.name, 
         print "not connected to correct controller"
         exit( 1 )
      controller.setIP( cintf, cip,  '/24' )
      switch.setIP( sintf, sip, '/24' )
      controller.setHostRoute( sip, cintf )
      switch.setHostRoute( cip, sintf )
   print
   print "*** Testing control network"
   while not controller.intfIsUp( controller.intfs[ 0 ] ):
      print "*** Waiting for ", controller.intfs[ 0 ], "to come up"
      sleep( 1 )
   for switch in switches:
      while not switch.intfIsUp( switch.intfs[ 0 ] ):
         print "*** Waiting for ", switch.intfs[ 0 ], "to come up"
         sleep( 1 )
   if pingTest( hosts=[ switch, controller ] ) != 0:
      print "*** Error: control network test failed"
      exit( 1 )

def configHosts( hosts, ips ):
   "Configure a set of hosts, starting at IP address a.b.c.d"
   for host in hosts:
      hintf = host.intfs[ 0 ]
      host.setIP( hintf, ips.next(), '/24' )
      host.setDefaultRoute( hintf )
      # You're low priority, dude!
      quietRun( 'renice +18 -p ' + `host.pid` )
      print host.name, ; flush()
   print
 
# Test driver and topologies

class Network( object ):
   "Network topology (and test driver) base class."
   def __init__( self,
      kernel=True, 
      Controller=Controller, Switch=Switch, 
      hostIpGen=ipGen, hostIpStart=( 192, 168, 123, 1 ) ):
      self.kernel = kernel
      self.Controller = Controller
      self.Switch = Switch
      self.hostIps = apply( hostIpGen, hostIpStart )
      # Check for kernel modules
      modules = quietRun( 'lsmod' )
      if not kernel and 'tun' not in modules:
         print "*** Error: kernel module tun not loaded:",
         print " user datapath not supported"
         exit( 1 )
      if kernel and 'ofdatapath' not in modules:
         print "*** Error: kernel module ofdatapath not loaded:",
         print " kernel datapath not supported"
         exit( 1 )
      # Create network, but don't start things up yet!
      self.prepareNet()
   def configureControlNetwork( self,
      ipGen=ipGen, ipStart = (10, 0, 123, 1 ) ):
      ips = apply( ipGen, ipStart )
      configureRoutedControlNetwork( self.controllers[ 0 ],
         self.switches, ips = ips)
   def configHosts( self ):
      configHosts( self.hosts, self.hostIps )
   def prepareNet( self ):
      """Create a network by calling makeNet as follows: 
         (switches, hosts ) = makeNet()
         Create a controller here as well."""
      kernel = self.kernel
      if kernel: print "*** Using kernel datapath"
      else: print "*** Using user datapath"
      print "*** Creating controller"
      self.controller = self.Controller( 'c0', kernel=kernel )
      self.controllers = [ self.controller ]
      print "*** Creating network"
      self.switches, self.hosts = self.makeNet( self.controller )
      print
      if not kernel:
         print "*** Configuring control network"
         self.configureControlNetwork()
      print "*** Configuring hosts"
      self.configHosts()
   def start( self ):
      "Start controller and switches"
      print "*** Starting controller"
      for controller in self.controllers:
         controller.start()
      print "*** Starting", len( self.switches ), "switches"
      for switch in self.switches:
         switch.start( self.controllers[ 0 ] )
   def stop( self ):
      "Stop the controller(s), switches and hosts"
      print "*** Stopping controller"
      for controller in self.controllers:
         controller.stop(); controller.terminate()
      print "*** Stopping switches"
      for switch in self.switches:
         print switch.name, ; flush()
         switch.stop() ; switch.terminate()
      print
      print "*** Stopping hosts"
      for host in self.hosts: 
         host.terminate()
      print "*** Test complete"
   def runTest( self, test ):
      "Run a given test, called as test( controllers, switches, hosts)"
      return test( self.controllers, self.switches, self.hosts )
   def run( self, test ):
      """Perform a complete start/test/stop cycle; test is of the form
         test( controllers, switches, hosts )"""
      self.start()
      print "*** Running test"
      result = self.runTest( test )
      self.stop()
      return result
   def interact( self ):
      "Create a network and run our simple CLI."
      self.run( self, Cli )
   
def defaultNames( snames=None, hnames=None, dpnames=None ):
   "Reinitialize default names from generators, if necessary."
   if snames is None: snames = nameGen( 's' )
   if hnames is None: hnames = nameGen( 'h' )
   if dpnames is None: dpnames = nameGen( 'nl:' )
   return snames, hnames, dpnames

# Tree network

class TreeNet( Network ):
   "A tree-structured network with the specified depth and fanout"
   def __init__( self, depth, fanout, **kwargs):
      self.depth, self.fanout = depth, fanout
      Network.__init__( self, **kwargs )
   def treeNet( self, controller, depth, fanout, kernel=True, snames=None,
      hnames=None, dpnames=None ):
      """Return a tree network of the given depth and fanout as a triple:
         ( root, switches, hosts ), using the given switch, host and
         datapath name generators, with the switches connected to the given
         controller. If kernel=True, use the kernel datapath; otherwise the
         user datapath will be used."""
      # Ugly, but necessary (?) since defaults are only evaluated once
      snames, hnames, dpnames = defaultNames( snames, hnames, dpnames )
      if ( depth == 0 ):
         host = Host( hnames.next() )
         print host.name, ; flush()
         return host, [], [ host ]
      dp = dpnames.next() if kernel else None
      switch = Switch( snames.next(), dp )
      if not kernel: createLink( switch, controller )
      print switch.name, ; flush()
      switches, hosts = [ switch ], []
      for i in range( 0, fanout ):
         child, slist, hlist = self.treeNet( controller, 
            depth - 1, fanout, kernel, snames, hnames, dpnames )
         createLink( switch, child )
         switches += slist
         hosts += hlist
      return switch, switches, hosts
   def makeNet( self, controller ):
      root, switches, hosts = self.treeNet( controller,
         self.depth, self.fanout, self.kernel)
      return switches, hosts
   
# Grid network

class GridNet( Network ):
   """An N x M grid/mesh network of switches, with hosts at the edges.
      This class also demonstrates creating a somewhat complicated
      topology."""
   def __init__( self, n, m, linear=False, **kwargs ):
      self.n, self.m, self.linear = n, m, linear and m == 1
      Network.__init__( self, **kwargs )
   def makeNet( self, controller ):
      snames, hnames, dpnames = defaultNames()
      n, m = self.n, self.m
      hosts = []
      switches = []
      kernel = self.kernel
      rows = []
      if not self.linear:
         print "*** gridNet: creating", n, "x", m, "grid of switches" ; flush()
      for y in range( 0, m ):
         row = []
         for x in range( 0, n ):
            dp = dpnames.next() if kernel else None
            switch = Switch( snames.next(), dp )
            if not kernel: createLink( switch, controller )
            row.append( switch )
            switches += [ switch ]
            print switch.name, ; flush()
         rows += [ row ]
      # Hook up rows
      for row in rows:
         previous = None
         for switch in row:
            if previous is not None:
               createLink( switch, previous )
            previous = switch
         h1, h2 = Host( hnames.next() ), Host( hnames.next() )
         createLink( h1, row[ 0 ] )
         createLink( h2, row[ -1 ] )
         hosts += [ h1, h2 ]
         print h1.name, h2.name, ; flush()
      # Return here if we're using this to make a linear network
      if self.linear: return switches, hosts
      # Hook up columns
      for x in range( 0, n ):
         previous = None
         for y in range( 0, m ):
            switch = rows[ y ][ x ]
            if previous is not None:
               createLink( switch, previous )
            previous = switch
         h1, h2 = Host( hnames.next() ), Host( hnames.next() )
         createLink( h1, rows[ 0 ][ x ] )
         createLink( h2, rows[ -1 ][ x ] )
         hosts += [ h1, h2 ]
         print h1.name, h2.name, ; flush()
      return switches, hosts

class LinearNet( GridNet ):
   def __init__( self, switchCount, kernel=True ):
      self.switchCount = switchCount
      GridNet.__init__( self, switchCount, 1, kernel, linear=True )
      
# Tests

def parsePing( pingOutput ):
   "Parse ping output and return packets sent, received."
   r = r'(\d+) packets transmitted, (\d+) received'
   m = re.search( r, pingOutput )
   if m == None:
      print "*** Error: could not parse ping output:", pingOutput
      exit( 1 )
   sent, received  = int( m.group( 1 ) ), int( m.group( 2 ) )
   return sent, received
   
def pingTest( controllers=[], switches=[], hosts=[], verbose=False ):
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

def pingTestVerbose( controllers, switches, hosts ):
   return "%d %% packet loss" % \
      pingTest( controllers, switches, hosts, verbose=True )
 
def parseIperf( iperfOutput ):
   "Parse iperf output and return bandwidth."
   r = r'([\d\.]+ \w+/sec)'
   m = re.search( r, iperfOutput )
   return m.group( 1 ) if m is not None else "could not parse iperf output"
    
def iperf( hosts, verbose=False ):
   "Run iperf between two hosts."
   assert len( hosts ) == 2
   host1, host2 = hosts[ 0 ], hosts[ 1 ]
   # dumpNodes( [ host1, host2 ] )
   host1.cmd( 'killall -9 iperf') # XXX shouldn't be global killall
   server = host1.cmd( 'iperf -s &' )
   if verbose: print server ; flush()
   client = host2.cmd( 'iperf -t 5 -c ' + host1.IP() )
   if verbose: print client ; flush()
   server = host1.cmd( 'kill -9 %iperf' )
   if verbose: print server; flush()
   return [ parseIperf( server ), parseIperf( client ) ]
   
def iperfTest( controllers, switches, hosts, verbose=False ):
   "Simple iperf test between two hosts."
   if verbose: print "*** Starting ping test"   
   h0, hN = hosts[ 0 ], hosts[ -1 ]
   print "*** iperfTest: Testing bandwidth between", 
   print h0.name, "and", hN.name
   result = iperf( [ h0, hN], verbose )
   print "*** result:", result
   return result

# Simple CLI

class Cli( object ):
   "Simple command-line interface to talk to nodes."
   cmds = [ '?', 'help', 'nodes', 'sh', 'pingtest', 'iperf', 'net', 'exit' ]
   def __init__( self, controllers, switches, hosts ):
      self.controllers = controllers
      self.switches = switches
      self.hosts = hosts
      self.nodemap = {}
      self.nodelist = controllers + switches + hosts
      for node in self.nodelist:
         self.nodemap[ node.name ] = node
      self.run()
   # Commands
   def help( self, args ):
      "Semi-useful help for CLI"
      print "Available commands are:", self.cmds
      print
      print "You may also send a command to a node using:"
      print "  <node> command {args}"
      print "For example:"
      print "  mininet> h0 ifconfig"
      print
      print "The interpreter automatically substitutes IP addresses"
      print "for node names, so commands like"
      print "  mininet> h0 ping -c1 h1"
      print "should work."
      print
      print "Interactive commands are not really supported yet,"
      print "so please limit commands to ones that do not"
      print "require user interaction and will terminate"
      print "after a reasonable amount of time."
   def nodes( self, args ):
      "List available nodes"
      print "available nodes are:", [ node.name for node in self.nodelist]
   def sh( self, args ):
      "Run an external shell command"
      call( [ 'sh', '-c' ] + args )
   def pingtest( self, args ):
      pingTest( self.controllers, self.switches, self.hosts, verbose=True )
   def net( self, args ):
      for switch in self.switches:
         print switch.name, "<->",
         for intf in switch.intfs:
            node, remoteIntf = switch.connection[ intf ]
            print node.name,
         print
   def iperf( self, args ):
      if len( args ) != 2:
         print "usage: iperf <h1> <h2>"
         return
      for host in args:
         if host not in self.nodemap:
            print "iperf: cannot find host:", host
            return
      iperf( [ self.nodemap[ h ] for h in args ], verbose=True )
   # Interpreter
   def run( self ):
      "Read and execute commands."
      print "*** cli: starting"
      while True:
         print "mininet> ", ; flush()
         input = sys.stdin.readline()
         if input == '': break
         if input[ -1 ] == '\n': input = input[ : -1 ]
         cmd = input.split( ' ' )
         first = cmd[ 0 ]
         rest = cmd[ 1: ]
         if first in self.cmds and hasattr( self, first ):
            getattr( self, first )( rest )
         elif first in self.nodemap and rest != []:
            node = self.nodemap[ first ]
            # Substitute IP addresses for node names in command
            rest = [ self.nodemap[ arg ].IP() if arg in self.nodemap else arg
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
         elif first == '?': self.help( rest )
         else: print "cli: unknown node or command: <", first, ">"
      print "*** cli: exiting"
   
def fixLimits():
   "Fix ridiculously small resource limits."
   setrlimit( RLIMIT_NPROC, ( 4096, 8192 ) )
   setrlimit( RLIMIT_NOFILE, ( 16384, 32768 ) )

def init():
   "Initialize Mininet."
   if os.getuid() != 0: 
      # Note: this script must be run as root 
      # Perhaps we should do so automatically!
      print "*** Mininet must run as root."; exit( 1 )
   # If which produces no output, then netns is not in the path.
   # May want to loosen this to handle netns in the current dir.
   if not quietRun( [ 'which', 'netns' ] ):
       raise Exception( "Could not find netns; see INSTALL" )
   fixLimits()

if __name__ == '__main__':
   init()
   results = {}
   print "*** Welcome to Mininet!"
   print "*** Look in examples/ for more examples\n"
   print "*** Testing Mininet with kernel and user datapath"
   for datapath in [ 'kernel', 'user' ]:
      k = datapath == 'kernel'
      network = TreeNet( depth=2, fanout=4, kernel=k)
      result = network.run( pingTestVerbose )
      results[ datapath ] = result
   print "*** Test results:", results
