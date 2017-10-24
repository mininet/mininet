#!/usr/bin/python

"""
Multiple ovsdb OVS!!
We scale up by creating multiple ovsdb instances,
each of which is shared by several OVS switches
The shell may also be shared among switch instances,
which causes switch.cmd() and switch.popen() to be
delegated to the ovsdb instance.
"""

import shutil
import sys

from mininet.net import Mininet
from mininet.node import RemoteController
from mininet.node import Node, OVSSwitch
from mininet.node import OVSBridge
from mininet.link import Link, OVSIntf
from mininet.topo import LinearTopo, SingleSwitchTopo
from mininet.topolib import TreeTopo
from mininet.log import setLogLevel, info
from mininet.cli import CLI
from mininet.clean import Cleanup, sh

from itertools import groupby
from operator import attrgetter

class OVSDB( Node ):
    "Namespace for an OVSDB instance"

    privateDirs = [ ('/etc/openvswitch', '/tmp/%(name)s'),
                    ('/var/run/openvswitch', '/tmp/%(name)s'),
                    ('/var/log/openvswitch', '/tmp/%(name)s') ]

    # Control network
    ipBase = '172.123.123.0/24'
    # Controller IP and Port
    controllerIP = None
    controllerPort = None
    cnet = None
    nat = None
    rlink = None

    @classmethod
    def startControlNet( cls, **kwargs ):
        "Start control net if necessary and return it"
        cnet = cls.cnet
        if not cnet:
            cls.controllerIP = kwargs.get('controllerIP', '127.0.0.1')
            cls.controllerPort = kwargs.get('controllerPort', 6633)
            natInUse = kwargs.get('natInUse', True)
            info( '### Starting control network\n' )
            cnet = Mininet( ipBase=cls.ipBase )
            cswitch = cnet.addSwitch( 'ovsbr0', cls=OVSBridge )
            cls.cnet = cnet
            if natInUse:
                #Add NAT - note this can conflict with data network NAT
                info('### Adding NAT for control and data networks'
                     ' (use --nat flush=0 for data network)\n')
                cls.nat = cnet.addNAT('ovsdbnat0')
            else:
                # connect ovsbr0 to root namespace
                cls.connectToRootNS(cnet.switches[0])
            cnet.start()
            info( '### Control network started\n' )
        return cnet

    @staticmethod
    def connectToRootNS(switch):
        # Create a node in root namespace and link to switch
        root = Node('root', inNamespace=False)
        OVSDB.rlink = Link(root, switch, intfName1="mn-eth1", intfName2="mn-peer1")
        # add interface to ovsbr0
        switch.attach(OVSDB.rlink.intf2)
        routes = [OVSDB.ipBase]
        for route in routes:
            root.cmd('ip route add ' + route + ' dev ' + str(OVSDB.rlink.intf1.name))

    def stopControlNet( self ):
        info( '\n### Stopping control network\n' )
        cls = self.__class__
        cls.cnet.stop()
        if self.nat is None:
            cls.rlink.stop()
        info( '### Control network stopped\n' )

    def addSwitch( self, switch ):
        "Add a switch to our namespace"
        # Attach first switch to cswitch!
        self.switches.append( switch )

    def delSwitch( self, switch ):
        "Delete a switch from our namespace, and terminate if none left"
        self.switches.remove( switch )
        if not self.switches:
            self.stopOVS()

    ovsdbCount = 0

    def startOVS( self ):
        "Start new OVS instance"
        self.cmd( 'ovsdb-tool create /etc/openvswitch/conf.db' )
        self.cmd( 'ovsdb-server /etc/openvswitch/conf.db'
                  ' -vfile:emer -vfile:err -vfile:info'
                  ' --remote=punix:/var/run/openvswitch/db.sock '
                  ' --log-file=/var/log/openvswitch/ovsdb-server.log'
                  ' --pidfile=/var/run/openvswitch/ovsdb-server-mn.pid'
                  ' --no-chdir'
                  ' --detach' )

        self.cmd( 'ovs-vswitchd unix:/var/run/openvswitch/db.sock'
                  ' -vfile:emer -vfile:err -vfile:info'
                  ' --mlockall --log-file=/var/log/openvswitch/ovs-vswitchd.log'
                  ' --pidfile=/var/run/openvswitch/ovs-vswitchd-mn.pid'
                  ' --no-chdir'
                  ' --detach' )

        self.cmd('ovs-vsctl set-manager tcp:' + str(self.controllerIP) + ':' + str(self.controllerPort))

        pid = self.cmd('cat /var/run/openvswitch/ovsdb-server-mn.pid')
        self.cmd('ovs-appctl -t ' + '/var/run/openvswitch/ovsdb-server.' + str(pid).rstrip() + '.ctl'
                 + ' ovsdb-server/add-remote db:Open_vSwitch,Open_vSwitch,manager_options')

    def stopOVS( self ):
        self.cmd( 'kill',
                  '`cat /var/run/openvswitch/ovs-vswitchd-mn.pid`',
                  '`cat /var/run/openvswitch/ovsdb-server-mn.pid`' )
        self.cmd( 'wait' )
        self.__class__.ovsdbCount -= 1
        for directory in self.privateDirs:
            if isinstance(directory, tuple):
                shutil.rmtree(directory[1] % {'name' : self.name}, ignore_errors=True)
        if self.__class__.ovsdbCount <= 0:
            self.stopControlNet()

    @classmethod
    def cleanUpOVS( cls ):
        "Clean up leftover ovsdb-server/ovs-vswitchd processes"
        info( '*** Shutting down extra ovsdb-server/ovs-vswitchd processes\n' )
        sh( 'pkill -f mn.pid' )

    def self( self, *args, **kwargs ):
        "A fake constructor that sets params and returns self"
        self.params = kwargs
        return self

    def __init__( self, **kwargs ):
        cls = self.__class__
        cls.ovsdbCount += 1
        cnet = self.startControlNet(**kwargs)
        # Create a new ovsdb namespace
        self.switches = []
        name = 'ovsdb%d' % cls.ovsdbCount
        kwargs.update( inNamespace=True )
        kwargs.setdefault( 'privateDirs', self.privateDirs )
        super( OVSDB, self ).__init__( name, **kwargs )
        ovsdb = cnet.addHost( name, cls=self.self, **kwargs )
        link = cnet.addLink( ovsdb, cnet.switches[ 0 ] )
        cnet.switches[ 0 ].attach( link.intf2 )
        ovsdb.configDefault()
        if self.nat is not None:
            ovsdb.setDefaultRoute( 'via %s' % self.nat.intfs[ 0 ].IP() )
        else:
            ovsdb.setDefaultRoute( 'via %s' % self.IP(self.defaultIntf()))
        ovsdb.startOVS()


# Install cleanup callback
Cleanup.addCleanupCallback( OVSDB.cleanUpOVS )


class OVSSwitchNS( OVSSwitch ):
    "OVS Switch in shared OVSNS namespace"

    isSetup = False

    @classmethod
    def batchStartup( cls, switches ):
        result = []
        for ovsdb, switchGroup in groupby( switches, attrgetter( 'ovsdb') ):
            switchGroup = list( switchGroup )
            info( '(%s)' % ovsdb )
            result += OVSSwitch.batchStartup( switchGroup, run=ovsdb.cmd )
        return result

    @classmethod
    def batchShutdown( cls, switches ):
        result = []
        for ovsdb, switchGroup in groupby( switches, attrgetter( 'ovsdb') ):
            switchGroup = list( switchGroup )
            info( '(%s)' % ovsdb )
            for switch in switches:
                if switch.pid == ovsdb.pid:
                    switch.pid = None
                    switch.shell = None
            result += OVSSwitch.batchShutdown( switchGroup, run=ovsdb.cmd )
            for switch in switchGroup:
                switch.ovsdbFree()
        return result

    # OVSDB allocation
    groupSize = 64
    switchCount = 0
    lastOvsdb = None
    controllerIP = None
    controllerPort = None
    nat = True

    @classmethod
    def ovsdbAlloc( cls, switch, **kwargs ):
        "Allocate (possibly new) OVSDB instance for switch"
        if cls.switchCount % switch.groupSize == 0:
            cls.lastOvsdb = OVSDB(**kwargs)
        cls.switchCount += 1
        cls.lastOvsdb.addSwitch( switch )
        return cls.lastOvsdb

    def ovsdbFree( self ):
        "Deallocate OVSDB instance for switch"
        self.ovsdb.delSwitch( self )

    def startShell( self, *args, **kwargs ):
        "Start shell in shared OVSDB namespace"
        kwargs['controllerIP'] = self.controllerIP
        kwargs['controllerPort'] = self.controllerPort
        kwargs['natInUse'] = self.nat
        ovsdb = self.ovsdbAlloc( self, **kwargs )
        kwargs.update( mnopts='-da %d ' % ovsdb.pid )
        self.ns = [ 'net' ]
        self.ovsdb = ovsdb
        self._waiting = False
        if self.privateShell:
            super( OVSSwitchNS, self ).startShell( *args, **kwargs )
        else:
            # Delegate methods and initialize local vars
            attrs = ( 'cmd', 'cmdPrint', 'sendCmd', 'waitOutput',
                      'monitor', 'write', 'read',
                      'pid', 'shell', 'stdout',)
            for attr in attrs:
                setattr( self, attr, getattr( ovsdb, attr ) )
        self.defaultIntf().updateIP()

    @property
    def waiting( self ):
        "Optionally delegated to ovsdb"
        return self._waiting if self.privateShell else self.ovsdb.waiting

    @waiting.setter
    def waiting( self, value ):
        "Optionally delegated to ovsdb (read only!)"
        if self.privateShell:
            _waiting = value

    def start( self, controllers ):
        "Update controller IP addresses if necessary"
        if self.nat:
             for controller in controllers:
                 if controller.IP() == '127.0.0.1' and not controller.intfs:
                    controller.intfs[ 0 ] = self.ovsdb.nat.intfs[ 0 ]
        super( OVSSwitchNS, self ).start( controllers )

    def stop( self, *args, **kwargs ):
        "Stop and free OVSDB namespace if necessary"
        self.ovsdbFree()

    def terminate( self, *args, **kwargs ):
        if self.privateShell:
            super( OVSSwitchNS, self ).terminate( *args, **kwargs )
        else:
            self.pid = None
            self.shell= None

    def defaultIntf( self ):
        return self.ovsdb.defaultIntf()

    def __init__( self, *args, **kwargs ):
        """n: number of OVS instances per OVSDB
           shell: run private shell/bash process? (False)
           If shell is shared/not private, cmd() and popen() are
           delegated to the OVSDB instance, which is different than
           regular OVSSwitch semantics!!"""
        self.groupSize = kwargs.pop( 'n', self.groupSize )
        self.privateShell = kwargs.pop( 'shell', False )
        self.controllerIP = kwargs.get('controllerIP', '127.0.0.1')
        self.controllerPort = kwargs.get('controllerPort', '6633')
        self.nat = kwargs.get('natInUse', True)
        super( OVSSwitchNS, self ).__init__( *args, **kwargs )


class OVSSwitchNSParams(OVSSwitchNS):

    controllerIP = '127.0.0.1'
    controllerPort = 6633

    @classmethod
    def setupControllerParams(cls):
        if len(sys.argv) > 2:
            cls.controllerIP = sys.argv[2]
        if len(sys.argv) > 3:
            cls.controllerPort = int(sys.argv[3])

    def __init__(self, *args, **kwargs):
        kwargs.update(n=1, shell=False, dpid="1", controllerIP=self.controllerIP, controllerPort=self.controllerPort, natInUse=False)
        super(OVSSwitchNSParams, self).__init__(*args, **kwargs)

class OVSLinkNS( Link ):
    "OVSLink that supports OVSSwitchNS"

    def __init__( self, node1, node2, **kwargs ):
        "See Link.__init__() for options"
        self.isPatchLink = False
        if ( isinstance( node1, OVSSwitch ) and
             isinstance( node2, OVSSwitch ) and
             getattr( node1, 'ovsdb', None ) ==
             getattr( node2, 'ovsdb', None ) ):
            self.isPatchLink = True
            kwargs.update( cls1=OVSIntf, cls2=OVSIntf )
        Link.__init__( self, node1, node2, **kwargs )

switches = { 'ovsns': OVSSwitchNS, 'ovsm': OVSSwitchNS }

links = { 'ovs': OVSLinkNS }

def test():
    "Test OVSNS switch"
    setLogLevel( 'info' )
    topo = TreeTopo(depth=4, fanout=2)
    net = Mininet( topo=topo, switch=OVSSwitchNS)
    # Add connectivity to controller which is on LAN or in root NS
    # net.addNAT().configDefault()
    net.start()
    CLI( net )
    net.stop()

def testWithParams():
    "Test OVSNS switch"
    "Usage: multiovs.py numHosts ControllerIP ControllerPort"
    setLogLevel('info')
    numHosts = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    topo = LinearTopo(numHosts)
    OVSSwitchNSParams.setupControllerParams()
    net = Mininet(topo=topo, switch=OVSSwitchNSParams, controller=RemoteController)
    net.start()
    CLI(net)
    net.stop()

if __name__ == '__main__':
    testWithParams()

