#!/usr/bin/python

from mininet.link import Link, Intf
from mininet.log import setLogLevel, debug, info, error
from mininet.util import quietRun, errRun


class RemoteLink( Link ):
    "A RemoteLink is a link between nodes which may be on different servers"

    def __init__( self, node1, node2, **kwargs ):
        """Initialize a RemoteLink
           see Link() for parameters"""
        # Create links on remote node
        self.node1 = node1
        self.node2 = node2
        self.tunnel = None
        kwargs.setdefault( 'params1', {} )
        kwargs.setdefault( 'params2', {} )
        self.cmd = None  # satisfy pylint
        port1 = port2 = intfName1 = intfName2 = cls1 = cls2 = fast = None
        intf = Intf

        # Dynamically create variable from kwargs
        for key, value in kwargs.iteritems():
            if isinstance(value, basestring):
                exec("{0}='{1}'".format(key, value))
            else:
                exec("{0}={1}".format(key, value))

        self.tunneling = tunneling

        if params2 is params1:
            params2 = dict( params1 )
        if port1 is not None:
            params1[ 'port' ] = port1
        if port2 is not None:
            params2[ 'port' ] = port2
        if 'port' not in params1:
            params1[ 'port' ] = node1.newPort()
        if 'port' not in params2:
            params2[ 'port' ] = node2.newPort()
        if not intfName1:
            intfName1 = self.intfName( node1, params1[ 'port' ] )
        if not intfName2:
            intfName2 = self.intfName( node2, params2[ 'port' ] )

        self.fast = fast
        if fast:
            params1.setdefault( 'moveIntfFn', self._ignore )
            params2.setdefault( 'moveIntfFn', self._ignore )
            self.makeIntfPair( intfName1, intfName2, addr1, addr2,
                               node1, node2, deleteIntfs=False )
        else:
            self.makeIntfPair( intfName1, intfName2, addr1, addr2 )

        if not cls1:
            cls1 = intf
        if not cls2:
            cls2 = intf

        intf1 = cls1( name=intfName1, node=node1,
                      link=self, mac=addr1, **params1  )
        intf2 = cls2( name=intfName2, node=node2,
                      link=self, mac=addr2, **params2 )

        self.intf1, self.intf2 = intf1, intf2


    def stop( self ):
        "Stop this link"
        if self.tunnel:
            self.tunnel.terminate()
            self.intf1.delete()
            self.intf2.delete()
        else:
            Link.stop( self )
        self.tunnel = None

    def makeIntfPair( self, intfname1, intfname2, addr1=None, addr2=None,
                      node1=None, node2=None, deleteIntfs=True   ):
        """Create pair of interfaces
            intfname1: name of interface 1
            intfname2: name of interface 2
            (override this method [and possibly delete()]
            to change link type)"""
        node1 = self.node1 if node1 is None else node1
        node2 = self.node2 if node2 is None else node2
        server1 = getattr( node1, 'server', 'localhost' )
        server2 = getattr( node2, 'server', 'localhost' )
        if server1 == server2:
            # Link within same server
            return Link.makeIntfPair( intfname1, intfname2, addr1, addr2,
                                      node1, node2, deleteIntfs=deleteIntfs )
        # Otherwise, make a tunnel
        self.tunnel = self.makeTunnel( node1, node2, intfname1, intfname2,
                                       addr1, addr2 )
        return self.tunnel

    @staticmethod
    def moveIntf( intf, node, printError=True ):
        """Move remote interface from root ns to node
            intf: string, interface
            dstNode: destination Node
            srcNode: source Node or None (default) for root ns
            printError: if true, print error"""
        intf = str( intf )
        cmd = 'ip link set %s netns %s' % ( intf, node.pid )
        node.rcmd( cmd )
        links = node.cmd( 'ip link show' )
        if not ' %s:' % intf in links:
            if printError:
                error( '*** Error: RemoteLink.moveIntf: ' + intf +
                       ' not successfully moved to ' + node.name + '\n' )
            return False
        return True

    def makeTunnel( self, node1, node2, intfname1, intfname2,
                    addr1=None, addr2=None ):
        "Make a tunnel across switches on different servers"
        # We should never try to create a tunnel to ourselves!
        assert node1.server != 'localhost' or node2.server != 'localhost'
        # And we can't ssh into this server remotely as 'localhost',
        # so try again swappping node1 and node2
        if node2.server == 'localhost':
            return self.makeTunnel( node2, node1, intfname2, intfname1,
                                    addr2, addr1 )
        # 1. Create tap interfaces
        for node in node1, node2:
            # For now we are hard-wiring tap9, which we will rename
            cmd = 'ip tuntap add dev tap9 mode tap user ' + node.user
            result = node.rcmd( cmd )
            if result:
                raise Exception( 'error creating tap9 on %s: %s' %
                                 ( node, result ) )
        # 2. Create ssh tunnel between tap interfaces
        # -n: close stdin
        dest = '%s@%s' % ( node2.user, node2.serverIP )
        cmd = [ 'ssh', '-n', '-o', 'Tunnel=Ethernet', '-w', '9:9',
                dest, 'echo @' ]
        self.cmd = cmd
        tunnel = node1.rpopen( cmd, sudo=False )
        # When we receive the character '@', it means that our
        # tunnel should be set up
        debug( 'Waiting for tunnel to come up...\n' )
        ch = tunnel.stdout.read( 1 )
        if ch != '@':
            raise Exception( 'makeTunnel:\n',
                             'Tunnel setup failed for',
                             '%s:%s' % ( node1, node1.dest ), 'to',
                             '%s:%s\n' % ( node2, node2.dest ),
                             'command was:', cmd, '\n' )
        # 3. Move interfaces if necessary
        for node in node1, node2:
            if not self.moveIntf( 'tap9', node ):
                raise Exception( 'interface move failed on node %s' % node )
        # 4. Rename tap interfaces to desired names
        for node, intf, addr in ( ( node1, intfname1, addr1 ),
                                  ( node2, intfname2, addr2 ) ):
            if not addr:
                result = node.cmd( 'ip link set tap9 name', intf )
            else:
                result = node.cmd( 'ip link set tap9 name', intf,
                                   'address', addr )
            if result:
                raise Exception( 'error renaming %s: %s' % ( intf, result ) )
        return tunnel

    def status( self ):
        "Detailed representation of link"
        if self.tunnel:
            if self.tunnel.poll() is not None:
                status = "Tunnel EXITED %s" % self.tunnel.returncode
            else:
                status = "Tunnel Running (%s: %s)" % (
                    self.tunnel.pid, self.cmd )
        else:
            status = "OK"
        result = "%s %s" % ( Link.status( self ), status )
        return result
