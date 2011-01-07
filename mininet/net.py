"""

    Mininet: A simple networking testbed for OpenFlow!

author: Bob Lantz (rlantz@cs.stanford.edu)
author: Brandon Heller (brandonh@stanford.edu)

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
link/etc.

This version supports both the kernel and user space datapaths
from the OpenFlow reference implementation (openflowswitch.org)
as well as OpenVSwitch (openvswitch.org.)

In kernel datapath mode, the controller and switches are simply
processes in the root namespace.

Kernel OpenFlow datapaths are instantiated using dpctl(8), and are
attached to the one side of a veth pair; the other side resides in the
host namespace. In this mode, switch processes can simply connect to the
controller via the loopback interface.

In user datapath mode, the controller and switches can be full-service
nodes that live in their own network namespaces and have management
interfaces and IP addresses on a control network (e.g. 192.168.123.1,
currently routed although it could be bridged.)

In addition to a management interface, user mode switches also have
several switch interfaces, halves of veth pairs whose other halves
reside in the host nodes that the switches are connected to.

Consistent, straightforward naming is important in order to easily
identify hosts, switches and controllers, both from the CLI and
from program code. Interfaces are named to make it easy to identify
which interfaces belong to which node.

The basic naming scheme is as follows:

    Host nodes are named h1-hN
    Switch nodes are named s1-sN
    Controller nodes are named c0-cN
    Interfaces are named {nodename}-eth0 .. {nodename}-ethN

Note: If the network topology is created using mininet.topo, then
node numbers are unique among hosts and switches (e.g. we have
h1..hN and SN..SN+M) and also correspond to their default IP addresses
of 10.x.y.z/8 where x.y.z is the base-256 representation of N for
hN. This mapping allows easy determination of a node's IP
address from its name, e.g. h1 -> 10.0.0.1, h257 -> 10.0.1.1.

Note also that 10.0.0.1 can often be written as 10.1 for short, e.g.
"ping 10.1" is equivalent to "ping 10.0.0.1".

Currently we wrap the entire network in a 'mininet' object, which
constructs a simulated network based on a network topology created
using a topology object (e.g. LinearTopo) from mininet.topo or
mininet.topolib, and a Controller which the switches will connect
to. Several configuration options are provided for functions such as
automatically setting MAC addresses, populating the ARP table, or
even running a set of terminals to allow direct interaction with nodes.

After the network is created, it can be started using start(), and a
variety of useful tasks maybe performed, including basic connectivity
and bandwidth tests and running the mininet CLI.

Once the network is up and running, test code can easily get access
to host and switch objects which can then be used for arbitrary
experiments, typically involving running a series of commands on the
hosts.

After all desired tests or activities have been completed, the stop()
method may be called to shut down the network.

"""

import os
import re
import select
import signal
from time import sleep

from mininet.cli import CLI
from mininet.log import info, error, debug, output
from mininet.node import Host, UserSwitch, OVSKernelSwitch, Controller
from mininet.node import ControllerParams
from mininet.util import quietRun, fixLimits
from mininet.util import createLink, macColonHex, ipStr, ipParse
from mininet.term import cleanUpScreens, makeTerms

class Mininet( object ):
    "Network emulation with hosts spawned in network namespaces."

    def __init__( self, topo=None, switch=OVSKernelSwitch, host=Host,
                 controller=Controller,
                 cparams=ControllerParams( '10.0.0.0', 8 ),
                 build=True, xterms=False, cleanup=False,
                 inNamespace=False,
                 autoSetMacs=False, autoStaticArp=False, listenPort=None ):
        """Create Mininet object.
           topo: Topo (topology) object or None
           switch: Switch class
           host: Host class
           controller: Controller class
           cparams: ControllerParams object
           build: build now from topo?
           xterms: if build now, spawn xterms?
           cleanup: if build now, cleanup before creating?
           inNamespace: spawn switches and controller in net namespaces?
           autoSetMacs: set MAC addrs from topo?
           autoStaticArp: set all-pairs static MAC addrs?
           listenPort: base listening port to open; will be incremented for
               each additional switch in the net if inNamespace=False"""
        self.switch = switch
        self.host = host
        self.controller = controller
        self.cparams = cparams
        self.topo = topo
        self.inNamespace = inNamespace
        self.xterms = xterms
        self.cleanup = cleanup
        self.autoSetMacs = autoSetMacs
        self.autoStaticArp = autoStaticArp
        self.listenPort = listenPort

        self.hosts = []
        self.switches = []
        self.controllers = []
        self.nameToNode = {}  # name to Node (Host/Switch) objects
        self.idToNode = {}  # dpid to Node (Host/Switch) objects
        self.dps = 0  # number of created kernel datapaths
        self.terms = []  # list of spawned xterm processes

        init()
        switch.setup()

        self.built = False
        if topo and build:
            self.build()

    def addHost( self, name, mac=None, ip=None ):
        """Add host.
           name: name of host to add
           mac: default MAC address for intf 0
           ip: default IP address for intf 0
           returns: added host"""
        host = self.host( name, defaultMAC=mac, defaultIP=ip )
        self.hosts.append( host )
        self.nameToNode[ name ] = host
        return host

    def addSwitch( self, name, mac=None, ip=None ):
        """Add switch.
           name: name of switch to add
           mac: default MAC address for kernel/OVS switch intf 0
           returns: added switch
           side effect: increments the listenPort member variable."""
        if self.switch == UserSwitch:
            sw = self.switch( name, listenPort=self.listenPort,
                defaultMAC=mac, defaultIP=ip, inNamespace=self.inNamespace )
        else:
            sw = self.switch( name, listenPort=self.listenPort,
                defaultMAC=mac, defaultIP=ip, dp=self.dps,
                inNamespace=self.inNamespace )
        if not self.inNamespace and self.listenPort:
            self.listenPort += 1
        self.dps += 1
        self.switches.append( sw )
        self.nameToNode[ name ] = sw
        return sw

    def addController( self, name='c0', controller=None, **kwargs ):
        """Add controller.
           controller: Controller class"""
        if not controller:
            controller = self.controller
        controller_new = controller( name, **kwargs )
        if controller_new:  # allow controller-less setups
            self.controllers.append( controller_new )
            self.nameToNode[ name ] = controller_new
        return controller_new

    # Control network support:
    #
    # Create an explicit control network. Currently this is only
    # used by the user datapath configuration.
    #
    # Notes:
    #
    # 1. If the controller and switches are in the same (e.g. root)
    #    namespace, they can just use the loopback connection.
    #
    # 2. If we can get unix domain sockets to work, we can use them
    #    instead of an explicit control network.
    #
    # 3. Instead of routing, we could bridge or use 'in-band' control.
    #
    # 4. Even if we dispense with this in general, it could still be
    #    useful for people who wish to simulate a separate control
    #    network (since real networks may need one!)

    def configureControlNetwork( self ):
        "Configure control network."
        self.configureRoutedControlNetwork()

    # We still need to figure out the right way to pass
    # in the control network location.

    def configureRoutedControlNetwork( self, ip='192.168.123.1',
        prefixLen=16 ):
        """Configure a routed control network on controller and switches.
           For use with the user datapath only right now.
           """
        controller = self.controllers[ 0 ]
        info( controller.name + ' <->' )
        cip = ip
        snum = ipParse( ip )
        for switch in self.switches:
            info( ' ' + switch.name )
            sintf, cintf = createLink( switch, controller )
            snum += 1
            while snum & 0xff in [ 0, 255 ]:
                snum += 1
            sip = ipStr( snum )
            controller.setIP( cintf, cip, prefixLen )
            switch.setIP( sintf, sip, prefixLen )
            controller.setHostRoute( sip, cintf )
            switch.setHostRoute( cip, sintf )
        info( '\n' )
        info( '*** Testing control network\n' )
        while not controller.intfIsUp( cintf ):
            info( '*** Waiting for', cintf, 'to come up\n' )
            sleep( 1 )
        for switch in self.switches:
            while not switch.intfIsUp( sintf ):
                info( '*** Waiting for', sintf, 'to come up\n' )
                sleep( 1 )
            if self.ping( hosts=[ switch, controller ] ) != 0:
                error( '*** Error: control network test failed\n' )
                exit( 1 )
        info( '\n' )

    def configHosts( self ):
        "Configure a set of hosts."
        # params were: hosts, ips
        for host in self.hosts:
            hintf = host.intfs[ 0 ]
            host.setIP( hintf, host.defaultIP, self.cparams.prefixLen )
            host.setDefaultRoute( hintf )
            # You're low priority, dude!
            quietRun( 'renice +18 -p ' + repr( host.pid ) )
            info( host.name + ' ' )
        info( '\n' )

    def buildFromTopo( self, topo ):
        """Build mininet from a topology object
           At the end of this function, everything should be connected
           and up."""

        def addNode( prefix, addMethod, nodeId ):
            "Add a host or a switch."
            name = prefix + topo.name( nodeId )
            mac = macColonHex( nodeId ) if self.setMacs else None
            ip = topo.ip( nodeId )
            node = addMethod( name, mac=mac, ip=ip )
            self.idToNode[ nodeId ] = node
            info( name + ' ' )

        # Possibly we should clean up here and/or validate
        # the topo
        if self.cleanup:
            pass

        info( '*** Adding controller\n' )
        self.addController( 'c0' )
        info( '*** Creating network\n' )
        info( '*** Adding hosts:\n' )
        for hostId in sorted( topo.hosts() ):
            addNode( 'h', self.addHost, hostId )
        info( '\n*** Adding switches:\n' )
        for switchId in sorted( topo.switches() ):
            addNode( 's', self.addSwitch, switchId )
        info( '\n*** Adding links:\n' )
        for srcId, dstId in sorted( topo.edges() ):
            src, dst = self.idToNode[ srcId ], self.idToNode[ dstId ]
            srcPort, dstPort = topo.port( srcId, dstId )
            createLink( src, dst, srcPort, dstPort )
            info( '(%s, %s) ' % ( src.name, dst.name ) )
        info( '\n' )

    def build( self ):
        "Build mininet."
        if self.topo:
            self.buildFromTopo( self.topo )
        if self.inNamespace:
            info( '*** Configuring control network\n' )
            self.configureControlNetwork()
        info( '*** Configuring hosts\n' )
        self.configHosts()
        if self.xterms:
            self.startTerms()
        if self.autoSetMacs:
            self.setMacs()
        if self.autoStaticArp:
            self.staticArp()
        self.built = True

    def startTerms( self ):
        "Start a terminal for each node."
        info( "*** Running terms on %s\n" % os.environ[ 'DISPLAY' ] )
        cleanUpScreens()
        self.terms += makeTerms( self.controllers, 'controller' )
        self.terms += makeTerms( self.switches, 'switch' )
        self.terms += makeTerms( self.hosts, 'host' )

    def stopXterms( self ):
        "Kill each xterm."
        # Kill xterms
        for term in self.terms:
            os.kill( term.pid, signal.SIGKILL )
        cleanUpScreens()

    def setMacs( self ):
        """Set MAC addrs to correspond to default MACs on hosts.
           Assume that the host only has one interface."""
        for host in self.hosts:
            host.setMAC( host.intfs[ 0 ], host.defaultMAC )

    def staticArp( self ):
        "Add all-pairs ARP entries to remove the need to handle broadcast."
        for src in self.hosts:
            for dst in self.hosts:
                if src != dst:
                    src.setARP( ip=dst.IP(), mac=dst.MAC() )

    def start( self ):
        "Start controller and switches."
        if not self.built:
            self.build()
        info( '*** Starting controller\n' )
        for controller in self.controllers:
            controller.start()
        info( '*** Starting %s switches\n' % len( self.switches ) )
        for switch in self.switches:
            info( switch.name + ' ')
            switch.start( self.controllers )
        info( '\n' )

    def stop( self ):
        "Stop the controller(s), switches and hosts"
        if self.terms:
            info( '*** Stopping %i terms\n' % len( self.terms ) )
            self.stopXterms()
        info( '*** Stopping %i hosts\n' % len( self.hosts ) )
        for host in self.hosts:
            info( '%s ' % host.name )
            host.terminate()
        info( '\n' )
        info( '*** Stopping %i switches\n' % len( self.switches ) )
        for switch in self.switches:
            info( switch.name )
            switch.stop()
        info( '\n' )
        info( '*** Stopping %i controllers\n' % len( self.controllers ) )
        for controller in self.controllers:
            controller.stop()
        info( '*** Done\n' )

    def run( self, test, *args, **kwargs ):
        "Perform a complete start/test/stop cycle."
        self.start()
        info( '*** Running test\n' )
        result = test( *args, **kwargs )
        self.stop()
        return result

    def monitor( self, hosts=None, timeoutms=-1 ):
        """Monitor a set of hosts (or all hosts by default),
           and return their output, a line at a time.
           hosts: (optional) set of hosts to monitor
           timeoutms: (optional) timeout value in ms
           returns: iterator which returns host, line"""
        if hosts is None:
            hosts = self.hosts
        poller = select.poll()
        Node = hosts[ 0 ]  # so we can call class method fdToNode
        for host in hosts:
            poller.register( host.stdout )
        while True:
            ready = poller.poll( timeoutms )
            for fd, event in ready:
                host = Node.fdToNode( fd )
                if event & select.POLLIN:
                    line = host.readline()
                    if line is not None:
                        yield host, line
            # Return if non-blocking
            if not ready and timeoutms >= 0:
                yield None, None

    @staticmethod
    def _parsePing( pingOutput ):
        "Parse ping output and return packets sent, received."
        # Check for downed link
        if 'connect: Network is unreachable' in pingOutput:
            return (1, 0)
        r = r'(\d+) packets transmitted, (\d+) received'
        m = re.search( r, pingOutput )
        if m == None:
            error( '*** Error: could not parse ping output: %s\n' %
                     pingOutput )
            return (1, 0)
        sent, received = int( m.group( 1 ) ), int( m.group( 2 ) )
        return sent, received

    def ping( self, hosts=None ):
        """Ping between all specified hosts.
           hosts: list of hosts
           returns: ploss packet loss percentage"""
        # should we check if running?
        packets = 0
        lost = 0
        ploss = None
        if not hosts:
            hosts = self.hosts
            output( '*** Ping: testing ping reachability\n' )
        for node in hosts:
            output( '%s -> ' % node.name )
            for dest in hosts:
                if node != dest:
                    result = node.cmd( 'ping -c1 ' + dest.IP() )
                    sent, received = self._parsePing( result )
                    packets += sent
                    if received > sent:
                        error( '*** Error: received too many packets' )
                        error( '%s' % result )
                        node.cmdPrint( 'route' )
                        exit( 1 )
                    lost += sent - received
                    output( ( '%s ' % dest.name ) if received else 'X ' )
            output( '\n' )
            ploss = 100 * lost / packets
        output( "*** Results: %i%% dropped (%d/%d lost)\n" %
                ( ploss, lost, packets ) )
        return ploss

    def pingAll( self ):
        """Ping between all hosts.
           returns: ploss packet loss percentage"""
        return self.ping()

    def pingPair( self ):
        """Ping between first two hosts, useful for testing.
           returns: ploss packet loss percentage"""
        hosts = [ self.hosts[ 0 ], self.hosts[ 1 ] ]
        return self.ping( hosts=hosts )

    @staticmethod
    def _parseIperf( iperfOutput ):
        """Parse iperf output and return bandwidth.
           iperfOutput: string
           returns: result string"""
        r = r'([\d\.]+ \w+/sec)'
        m = re.findall( r, iperfOutput )
        if m:
            return m[-1]
        else:
            # was: raise Exception(...)
            error( 'could not parse iperf output: ' + iperfOutput )
            return ''

    def iperf( self, hosts=None, l4Type='TCP', udpBw='10M' ):
        """Run iperf between two hosts.
           hosts: list of hosts; if None, uses opposite hosts
           l4Type: string, one of [ TCP, UDP ]
           returns: results two-element array of server and client speeds"""
        if not quietRun( 'which telnet' ):
            error( 'Cannot find telnet in $PATH - required for iperf test' )
            return
        if not hosts:
            hosts = [ self.hosts[ 0 ], self.hosts[ -1 ] ]
        else:
            assert len( hosts ) == 2
        client, server = hosts
        output( '*** Iperf: testing ' + l4Type + ' bandwidth between ' )
        output( "%s and %s\n" % ( client.name, server.name ) )
        server.cmd( 'killall -9 iperf' )
        iperfArgs = 'iperf '
        bwArgs = ''
        if l4Type == 'UDP':
            iperfArgs += '-u '
            bwArgs = '-b ' + udpBw + ' '
        elif l4Type != 'TCP':
            raise Exception( 'Unexpected l4 type: %s' % l4Type )
        server.sendCmd( iperfArgs + '-s', printPid=True )
        servout = ''
        while server.lastPid is None:
            servout += server.monitor()
        while 'Connected' not in client.cmd(
            'sh -c "echo A | telnet -e A %s 5001"' % server.IP()):
            output('waiting for iperf to start up')
            sleep(.5)
        cliout = client.cmd( iperfArgs + '-t 5 -c ' + server.IP() + ' ' +
                           bwArgs )
        debug( 'Client output: %s\n' % cliout )
        server.sendInt()
        servout += server.waitOutput()
        debug( 'Server output: %s\n' % servout )
        result = [ self._parseIperf( servout ), self._parseIperf( cliout ) ]
        if l4Type == 'UDP':
            result.insert( 0, udpBw )
        output( '*** Results: %s\n' % result )
        return result

    def configLinkStatus( self, src, dst, status ):
        """Change status of src <-> dst links.
           src: node name
           dst: node name
           status: string {up, down}"""
        if src not in self.nameToNode:
            error( 'src not in network: %s\n' % src )
        elif dst not in self.nameToNode:
            error( 'dst not in network: %s\n' % dst )
        else:
            srcNode, dstNode = self.nameToNode[ src ], self.nameToNode[ dst ]
            connections = srcNode.connectionsTo( dstNode )
            if len( connections ) == 0:
                error( 'src and dst not connected: %s %s\n' % ( src, dst) )
            for srcIntf, dstIntf in connections:
                result = srcNode.cmd( 'ifconfig', srcIntf, status )
                if result:
                    error( 'link src status change failed: %s\n' % result )
                result = dstNode.cmd( 'ifconfig', dstIntf, status )
                if result:
                    error( 'link dst status change failed: %s\n' % result )

    def interact( self ):
        "Start network and run our simple CLI."
        self.start()
        result = CLI( self )
        self.stop()
        return result


# pylint thinks inited is unused
# pylint: disable-msg=W0612

def init():
    "Initialize Mininet."
    if init.inited:
        return
    if os.getuid() != 0:
        # Note: this script must be run as root
        # Perhaps we should do so automatically!
        print "*** Mininet must run as root."
        exit( 1 )
    # If which produces no output, then mnexec is not in the path.
    # May want to loosen this to handle mnexec in the current dir.
    if not quietRun( 'which mnexec' ):
        raise Exception( "Could not find mnexec - check $PATH" )
    fixLimits()
    init.inited = True

init.inited = False

# pylint: enable-msg=W0612
