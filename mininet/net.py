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
from the OpenFlow reference implementation.

In kernel datapath mode, the controller and switches are simply
processes in the root namespace.

Kernel OpenFlow datapaths are instantiated using dpctl(8), and are
attached to the one side of a veth pair; the other side resides in the
host namespace. In this mode, switch processes can simply connect to the
controller via the loopback interface.

In user datapath mode, the controller and switches can be full-service
nodes that live in their own network namespaces and have management
interfaces and IP addresses on a control network (e.g. 10.0.123.1,
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
    Switch nodes are named s0-sN
    Controller nodes are named c0-cN
    Interfaces are named {nodename}-eth0 .. {nodename}-ethN

Currently we wrap the entire network in a 'mininet' object, which
constructs a simulated network based on a network topology created
using a topology object (e.g. LinearTopo) from topo.py and a Controller
node which the switches will connect to.  Several
configuration options are provided for functions such as
automatically setting MAC addresses, populating the ARP table, or
even running a set of xterms to allow direct interaction with nodes.

After the mininet is created, it can be started using start(), and a variety
of useful tasks maybe performed, including basic connectivity and
bandwidth tests and running the mininet CLI.

Once the network is up and running, test code can easily get access
to its host and switch objects, which can then be used
for arbitrary experiments, which typically involve running a series of
commands on the hosts.

After all desired tests or activities have been completed, the stop()
method may be called to shut down the network.

"""

import os
import re
import signal
from time import sleep

from mininet.cli import CLI
from mininet.log import info, error
from mininet.node import KernelSwitch, OVSKernelSwitch
from mininet.util import quietRun, fixLimits
from mininet.util import makeIntfPair, moveIntf
from mininet.xterm import cleanUpScreens, makeXterms

DATAPATHS = [ 'kernel' ] #[ 'user', 'kernel' ]

def init():
    "Initialize Mininet."
    if os.getuid() != 0:
        # Note: this script must be run as root
        # Perhaps we should do so automatically!
        print "*** Mininet must run as root."
        exit( 1 )
    # If which produces no output, then netns is not in the path.
    # May want to loosen this to handle netns in the current dir.
    if not quietRun( [ 'which', 'netns' ] ):
        raise Exception( "Could not find netns; see INSTALL" )
    fixLimits()

class Mininet( object ):
    "Network emulation with hosts spawned in network namespaces."

    def __init__( self, topo, switch, host, controller, cparams,
                 build=True, xterms=False, cleanup=False,
                 inNamespace=False,
                 autoSetMacs=False, autoStaticArp=False ):
        """Create Mininet object.
           topo: Topo object
           switch: Switch class
           host: Host class
           controller: Controller class
           cparams: ControllerParams object
           now: build now?
           xterms: if build now, spawn xterms?
           cleanup: if build now, cleanup before creating?
           inNamespace: spawn switches and controller in net namespaces?
           autoSetMacs: set MAC addrs to DPIDs?
           autoStaticArp: set all-pairs static MAC addrs?"""
        self.topo = topo
        self.switch = switch
        self.host = host
        self.controller = controller
        self.cparams = cparams
        self.nodes = {} # dpid to Node{ Host, Switch } objects
        self.controllers = {} # controller name to Controller objects
        self.dps = 0 # number of created kernel datapaths
        self.inNamespace = inNamespace
        self.xterms = xterms
        self.cleanup = cleanup
        self.autoSetMacs = autoSetMacs
        self.autoStaticArp = autoStaticArp

        self.terms = [] # list of spawned xterm processes

        if build:
            self.build()

    def _addHost( self, dpid ):
        """Add host.
           dpid: DPID of host to add"""
        host = self.host( 'h' + self.topo.name( dpid ) )
        # for now, assume one interface per host.
        host.intfs.append( 'h' + self.topo.name( dpid ) + '-eth0' )
        self.nodes[ dpid ] = host
        #info( '%s ' % host.name )

    def _addSwitch( self, dpid ):
        """Add switch.
           dpid: DPID of switch to add"""
        sw = None
        swDpid = None
        if self.autoSetMacs:
            swDpid = dpid
        if self.switch is KernelSwitch or self.switch is OVSKernelSwitch:
            sw = self.switch( 's_' + self.topo.name( dpid ), dp = self.dps,
                             dpid = swDpid )
            self.dps += 1
        else:
            sw = self.switch( 's_' + self.topo.name( dpid ) )
        self.nodes[ dpid ] = sw

    def _addLink( self, src, dst ):
        """Add link.
           src: source DPID
           dst: destination DPID"""
        srcPort, dstPort = self.topo.port( src, dst )
        srcNode = self.nodes[ src ]
        dstNode = self.nodes[ dst ]
        srcIntf = srcNode.intfName( srcPort )
        dstIntf = dstNode.intfName( dstPort )
        makeIntfPair( srcIntf, dstIntf )
        srcNode.intfs.append( srcIntf )
        dstNode.intfs.append( dstIntf )
        srcNode.ports[ srcPort ] = srcIntf
        dstNode.ports[ dstPort ] = dstIntf
        #info( '\n' )
        #info( 'added intf %s to src node %x\n' % ( srcIntf, src ) )
        #info( 'added intf %s to dst node %x\n' % ( dstIntf, dst ) )
        if srcNode.inNamespace:
            #info( 'moving src w/inNamespace set\n' )
            moveIntf( srcIntf, srcNode )
        if dstNode.inNamespace:
            #info( 'moving dst w/inNamespace set\n' )
            moveIntf( dstIntf, dstNode )
        srcNode.connection[ srcIntf ] = ( dstNode, dstIntf )
        dstNode.connection[ dstIntf ] = ( srcNode, srcIntf )

    def _addController( self, controller ):
        """Add controller.
           controller: Controller class"""
        controller = self.controller( 'c0', self.inNamespace )
        if controller: # allow controller-less setups
            self.controllers[ 'c0' ] = controller

    # Control network support:
    #
    # Create an explicit control network. Currently this is only
    # used by the user datapath configuration.
    #
    # Notes:
    #
    # 1. If the controller and switches are in the same ( e.g. root )
    #    namespace, they can just use the loopback connection.
    #    We may wish to do this for the user datapath as well as the
    #    kernel datapath.
    #
    # 2. If we can get unix domain sockets to work, we can use them
    #    instead of an explicit control network.
    #
    # 3. Instead of routing, we could bridge or use 'in-band' control.
    #
    # 4. Even if we dispense with this in general, it could still be
    #    useful for people who wish to simulate a separate control
    #    network ( since real networks may need one! )

    def _configureControlNetwork( self ):
        "Configure control network."
        self._configureRoutedControlNetwork()

    def _configureRoutedControlNetwork( self ):
        """Configure a routed control network on controller and switches.
           For use with the user datapath only right now.
           TODO( brandonh ) test this code!
           """
        # params were: controller, switches, ips

        controller = self.controllers[ 'c0' ]
        info( '%s <-> ' % controller.name )
        for switchDpid in self.topo.switches():
            switch = self.nodes[ switchDpid ]
            info( '%s ' % switch.name )
            sip = self.topo.ip( switchDpid )#ips.next()
            sintf = switch.intfs[ 0 ]
            node, cintf = switch.connection[ sintf ]
            if node != controller:
                error( '*** Error: switch %s not connected to correct'
                         'controller' %
                         switch.name )
                exit( 1 )
            controller.setIP( cintf, self.cparams.ip, '/' +
                             self.cparams.subnetSize )
            switch.setIP( sintf, sip, '/' + self.cparams.subnetSize )
            controller.setHostRoute( sip, cintf )
            switch.setHostRoute( self.cparams.ip, sintf )
        info( '\n' )
        info( '*** Testing control network\n' )
        while not controller.intfIsUp( controller.intfs[ 0 ] ):
            info( '*** Waiting for %s to come up\n',
                controller.intfs[ 0 ] )
            sleep( 1 )
        for switchDpid in self.topo.switches():
            switch = self.nodes[ switchDpid ]
            while not switch.intfIsUp( switch.intfs[ 0 ] ):
                info( '*** Waiting for %s to come up\n' %
                    switch.intfs[ 0 ] )
                sleep( 1 )
            if self.ping( hosts=[ switch, controller ] ) != 0:
                error( '*** Error: control network test failed\n' )
                exit( 1 )
        info( '\n' )

    def _configHosts( self ):
        "Configure a set of hosts."
        # params were: hosts, ips
        for hostDpid in self.topo.hosts():
            host = self.nodes[ hostDpid ]
            hintf = host.intfs[ 0 ]
            host.setIP( hintf, self.topo.ip( hostDpid ),
                       '/' + str( self.cparams.subnetSize ) )
            host.setDefaultRoute( hintf )
            # You're low priority, dude!
            quietRun( 'renice +18 -p ' + repr( host.pid ) )
            info( '%s ', host.name )
        info( '\n' )

    def build( self ):
        """Build mininet.
           At the end of this function, everything should be connected
           and up."""
        if self.cleanup:
            pass # cleanup
        # validate topo?
        info( '*** Adding controller\n' )
        self._addController( self.controller )
        info( '*** Creating network\n' )
        info( '*** Adding hosts:\n' )
        for host in sorted( self.topo.hosts() ):
            self._addHost( host )
            info( '0x%x ' % host )
        info( '\n*** Adding switches:\n' )
        for switch in sorted( self.topo.switches() ):
            self._addSwitch( switch )
            info( '0x%x ' % switch )
        info( '\n*** Adding edges:\n' )
        for src, dst in sorted( self.topo.edges() ):
            self._addLink( src, dst )
            info( '(0x%x, 0x%x) ' % ( src, dst ) )
        info( '\n' )

        if self.inNamespace:
            info( '*** Configuring control network\n' )
            self._configureControlNetwork()

        info( '*** Configuring hosts\n' )
        self._configHosts()

        if self.xterms:
            self.startXterms()
        if self.autoSetMacs:
            self.setMacs()
        if self.autoStaticArp:
            self.staticArp()

    def switchNodes( self ):
        "Return switch nodes."
        return [ self.nodes[ dpid ] for dpid in self.topo.switches() ]

    def hostNodes( self ):
        "Return host nodes."
        return [ self.nodes[ dpid ] for dpid in self.topo.hosts() ]

    def startXterms( self ):
        "Start an xterm for each node in the topo."
        info( "*** Running xterms on %s\n" % os.environ[ 'DISPLAY' ] )
        cleanUpScreens()
        self.terms += makeXterms( self.controllers.values(), 'controller' )
        self.terms += makeXterms( self.switchNodes(), 'switch' )
        self.terms += makeXterms( self.hostNodes(), 'host' )

    def stopXterms( self ):
        "Kill each xterm."
        # Kill xterms
        for term in self.terms:
            os.kill( term.pid, signal.SIGKILL )
        cleanUpScreens()

    def setMacs( self ):
        """Set MAC addrs to correspond to datapath IDs on hosts.
           Assume that the host only has one interface."""
        for dpid in self.topo.hosts():
            hostNode = self.nodes[ dpid ]
            hostNode.setMAC( hostNode.intfs[ 0 ], dpid )

    def staticArp( self ):
        "Add all-pairs ARP entries to remove the need to handle broadcast."
        for src in self.topo.hosts():
            srcNode = self.nodes[ src ]
            for dst in self.topo.hosts():
                if src != dst:
                    srcNode.setARP( dst, dst )

    def start( self ):
        "Start controller and switches"
        info( '*** Starting controller\n' )
        for cnode in self.controllers.values():
            cnode.start()
        info( '*** Starting %s switches\n' % len( self.topo.switches() ) )
        for switchDpid in self.topo.switches():
            switch = self.nodes[ switchDpid ]
            #info( 'switch = %s' % switch )
            info( '0x%x ' % switchDpid )
            switch.start( self.controllers )
        info( '\n' )

    def stop( self ):
        "Stop the controller(s), switches and hosts"
        if self.terms:
            info( '*** Stopping %i terms\n' % len( self.terms ) )
            self.stopXterms()
        info( '*** Stopping %i hosts\n' % len( self.topo.hosts() ) )
        for hostDpid in self.topo.hosts():
            host = self.nodes[ hostDpid ]
            info( '%s ' % host.name )
            host.terminate()
        info( '\n' )
        info( '*** Stopping %i switches\n' % len( self.topo.switches() ) )
        for switchDpid in self.topo.switches():
            switch = self.nodes[ switchDpid ]
            info( '%s' % switch.name )
            switch.stop()
        info( '\n' )
        info( '*** Stopping controller\n' )
        for cnode in self.controllers.values():
            cnode.stop()
        info( '*** Test complete\n' )

    def run( self, test, **params ):
        "Perform a complete start/test/stop cycle."
        self.start()
        info( '*** Running test\n' )
        result = getattr( self, test )( **params )
        self.stop()
        return result

    @staticmethod
    def _parsePing( pingOutput ):
        "Parse ping output and return packets sent, received."
        r = r'(\d+) packets transmitted, (\d+) received'
        m = re.search( r, pingOutput )
        if m == None:
            error( '*** Error: could not parse ping output: %s\n' %
                     pingOutput )
            exit( 1 )
        sent, received = int( m.group( 1 ) ), int( m.group( 2 ) )
        return sent, received

    def ping( self, hosts=None ):
        """Ping between all specified hosts.
           hosts: list of host DPIDs
           returns: ploss packet loss percentage"""
        #self.start()
        # check if running - only then, start?
        packets = 0
        lost = 0
        ploss = None
        if not hosts:
            hosts = self.topo.hosts()
        info( '*** Ping: testing ping reachability\n' )
        for nodeDpid in hosts:
            node = self.nodes[ nodeDpid ]
            info( '%s -> ' % node.name )
            for destDpid in hosts:
                dest = self.nodes[ destDpid ]
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
                    info( ( '%s ' % dest.name ) if received else 'X ' )
            info( '\n' )
            ploss = 100 * lost / packets
        info( "*** Results: %i%% dropped (%d/%d lost)\n" %
                ( ploss, lost, packets ) )
        return ploss

    def pingAll( self ):
        """Ping between all hosts.
           returns: ploss packet loss percentage"""
        return self.ping()

    def pingPair( self ):
        """Ping between first two hosts, useful for testing.
           returns: ploss packet loss percentage"""
        hostsSorted = sorted( self.topo.hosts() )
        hosts = [ hostsSorted[ 0 ], hostsSorted[ 1 ] ]
        return self.ping( hosts=hosts )

    @staticmethod
    def _parseIperf( iperfOutput ):
        """Parse iperf output and return bandwidth.
           iperfOutput: string
           returns: result string"""
        r = r'([\d\.]+ \w+/sec)'
        m = re.search( r, iperfOutput )
        if m:
            return m.group( 1 )
        else:
            raise Exception( 'could not parse iperf output' )

    def iperf( self, hosts=None, l4Type='TCP', udpBw='10M',
              verbose=False ):
        """Run iperf between two hosts.
           hosts: list of host DPIDs; if None, uses opposite hosts
           l4Type: string, one of [ TCP, UDP ]
           verbose: verbose printing
           returns: results two-element array of server and client speeds"""
        if not hosts:
            hostsSorted = sorted( self.topo.hosts() )
            hosts = [ hostsSorted[ 0 ], hostsSorted[ -1 ] ]
        else:
            assert len( hosts ) == 2
        host0 = self.nodes[ hosts[ 0 ] ]
        host1 = self.nodes[ hosts[ 1 ] ]
        info( '*** Iperf: testing ' + l4Type + ' bandwidth between ' )
        info( "%s and %s\n" % ( host0.name, host1.name ) )
        host0.cmd( 'killall -9 iperf' )
        iperfArgs = 'iperf '
        bwArgs = ''
        if l4Type == 'UDP':
            iperfArgs += '-u '
            bwArgs = '-b ' + udpBw + ' '
        elif l4Type != 'TCP':
            raise Exception( 'Unexpected l4 type: %s' % l4Type )
        server = host0.cmd( iperfArgs + '-s &' )
        if verbose:
            info( '%s\n' % server )
        client = host1.cmd( iperfArgs + '-t 5 -c ' + host0.IP() + ' ' +
                           bwArgs )
        if verbose:
            info( '%s\n' % client )
        server = host0.cmd( 'killall -9 iperf' )
        if verbose:
            info( '%s\n' % server )
        result = [ self._parseIperf( server ), self._parseIperf( client ) ]
        if l4Type == 'UDP':
            result.insert( 0, udpBw )
        info( '*** Results: %s\n' % result )
        return result

    def iperfUdp( self, udpBw='10M' ):
        "Run iperf UDP test."
        return self.iperf( l4Type='UDP', udpBw=udpBw )

    def interact( self ):
        "Start network and run our simple CLI."
        self.start()
        result = CLI( self )
        self.stop()
        return result
