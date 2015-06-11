#!/usr/bin/python

"""
Multiple ovsdb OVS!!

We scale up by creating multiple ovsdb instances,
each of which is shared by several OVS switches

"""

from mininet.net import Mininet
from mininet.node import Node, OVSSwitch
from mininet.node import OVSBridge
from mininet.link import Link, OVSLink
from mininet.topo import LinearTopo, SingleSwitchTopo
from mininet.topolib import TreeTopo
from mininet.log import setLogLevel, info
from mininet.cli import CLI

from itertools import groupby
from operator import attrgetter

class OVSDB( Node ):
    "Namespace for an OVSDB instance"

    privateDirs = [ '/etc/openvswitch',
                    '/var/run/openvswitch',
                    '/var/log/openvswitch' ]

    # Control network
    ipBase = '10.123.123.0/24'
    cnet = None
    nat = None

    @classmethod
    def startControlNet( cls ):
        "Start control net if necessary and return it"
        cnet = cls.cnet
        if not cnet:
            info( '### Starting control network\n' )
            cnet = Mininet( ipBase=cls.ipBase )
            cswitch = cnet.addSwitch( 'ovsbr0', cls=OVSBridge )
            # Add NAT - note this can conflict with data network NAT
            info( '### Adding NAT for control and data networks'
                  ' (use --nat flush=0 for data network)\n' )
            cls.cnet = cnet
            cls.nat = cnet.addNAT( 'ovsdbnat0')
            cnet.start()
            info( '### Control network started\n' )
        return cnet
    
    def stopControlNet( self ):
        info( '\n### Stopping control network\n' )
        cls = self.__class__
        cls.cnet.stop()
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
                  ' --pidfile=/var/run/openvswitch/ovsdb-server.pid'
                  ' --no-chdir'
                  ' --detach' )

        self.cmd( 'ovs-vswitchd unix:/var/run/openvswitch/db.sock'
                  ' -vfile:emer -vfile:err -vfile:info'
                  ' --mlockall --log-file=/var/log/openvswitch/ovs-vswitchd.log'
                  ' --pidfile=/var/run/openvswitch/ovs-vswitchd.pid'
                  ' --no-chdir'
                  ' --detach' )

    def stopOVS( self ):
        self.cmd( 'kill',
                  '`cat /var/run/openvswitch/ovs-vswitchd.pid`',
                  '`cat /var/run/openvswitch/ovsdb-server.pid`' )
        self.cmd( 'wait' )
        self.__class__.ovsdbCount -= 1
        if self.__class__.ovsdbCount <= 0:
            self.stopControlNet()

    def self( self, *args, **kwargs ):
        "A fake constructor that sets params and returns self"
        self.params = kwargs
        return self

    def __init__( self, **kwargs ):
        cls = self.__class__
        cls.ovsdbCount += 1
        cnet = self.startControlNet()
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
        ovsdb.setDefaultRoute( 'via %s' % self.nat.intfs[ 0 ].IP() )
        ovsdb.startOVS()


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
            result += OVSSwitch.batchShutdown( switchGroup, run=ovsdb.cmd )
            for switch in switchGroup:
                switch.ovsdbFree()
        return result

    # OVSDB allocation
    groupSize = 64
    switchCount = 0
    lastOvsdb = None

    @classmethod
    def ovsdbAlloc( cls, switch ):
        "Allocate (possibly new) OVSDB instance for switch"
        if cls.switchCount % switch.groupSize == 0:
            cls.lastOvsdb = OVSDB()
        cls.switchCount += 1
        cls.lastOvsdb.addSwitch( switch )
        return cls.lastOvsdb

    def ovsdbFree( self ):
        "Deallocate OVSDB instance for switch"
        self.ovsdb.delSwitch( self )

    def startShell( self, *args, **kwargs ):
        "Start shell in shared OVSDB namespace"
        ovsdb = self.ovsdbAlloc( self )
        kwargs.update( mnopts='-da %d ' % ovsdb.pid )
        self.ns = [ 'net' ]
        self.ovsdb = ovsdb
        super( OVSSwitchNS, self ).startShell( *args, **kwargs )
        self.defaultIntf().updateIP()

    def start( self, controllers ):
        "Update controller IP addresses if necessary"
        for controller in controllers:
            if controller.IP() == '127.0.0.1' and not controller.intfs:
                controller.intfs[ 0 ] = self.ovsdb.nat.intfs[ 0 ]
        super( OVSSwitchNS, self ).start( controllers )

    def stop( self, *args, **kwargs ):
        "Stop and free OVSDB namespace if necessary"
        super( OVSSwitchNS, self ).stop( *args, **kwargs )
        self.ovsdbFree()

    def defaultIntf( self ):
        return self.ovsdb.defaultIntf()

    def __init__( self, *args, **kwargs ):
        "group: number of OVS instances per OVSDB"
        self.groupSize = kwargs.pop( 'group', self.groupSize )
        super( OVSSwitchNS, self ).__init__( *args, **kwargs )


switches = { 'ovsns': OVSSwitchNS, 'ovsm': OVSSwitchNS }


def test():
    "Test OVSNS switch"
    setLogLevel( 'info' )
    topo = TreeTopo( depth=4, fanout=2 )
    net = Mininet( topo=topo, switch=OVSSwitchNS )
    # Add connectivity to controller which is on LAN or in root NS
    # net.addNAT().configDefault()
    net.start()
    CLI( net )
    net.stop()


if __name__ == '__main__':
    test()
