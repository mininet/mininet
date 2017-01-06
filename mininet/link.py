"""
link.py: interface and link abstractions for mininet

It seems useful to bundle functionality for interfaces into a single
class.

Also it seems useful to enable the possibility of multiple flavors of
links, including:

- simple veth pairs
- tunneled links
- patchable links (which can be disconnected and reconnected via a patchbay)
- link simulators (e.g. wireless)

Basic division of labor:

  Nodes: know how to execute commands
  Intfs: know how to configure themselves
  Links: know how to connect nodes together

Intf: basic interface object that can configure itself
TCIntf: interface with bandwidth limiting and delay via tc

Link: basic link class for creating veth pairs
"""

from mininet.log import info, error, debug
from mininet.util import makeIntfPair
import re

class Intf( object ):

    "Basic interface object that can configure itself."

    def __init__( self, name, node=None, port=None, link=None,
                  mac=None, **params ):
        """name: interface name (e.g. h1-eth0)
           node: owning node (where this intf most likely lives)
           link: parent link if we're part of a link
           other arguments are passed to config()"""
        self.node = node
        self.name = name
        self.link = link
        self.mac = mac
        self.ip, self.prefixLen = None, None

        # if interface is lo, we know the ip is 127.0.0.1.
        # This saves an ifconfig command per node
        if self.name == 'lo':
            self.ip = '127.0.0.1'
            self.prefixLen = 8
        # Add to node (and move ourselves if necessary )
        moveIntfFn = params.pop( 'moveIntfFn', None )
        if moveIntfFn:
            node.addIntf( self, port=port, moveIntfFn=moveIntfFn )
        else:
            node.addIntf( self, port=port )
        # Save params for future reference
        self.params = params
        self.config( **params )

    def cmd( self, *args, **kwargs ):
        "Run a command in our owning node"
        return self.node.cmd( *args, **kwargs )

    def ifconfig( self, *args ):
        "Configure ourselves using ifconfig"
        return self.cmd( 'ifconfig', self.name, *args )

    def setIP( self, ipstr, prefixLen=None ):
        """Set our IP address"""
        # This is a sign that we should perhaps rethink our prefix
        # mechanism and/or the way we specify IP addresses
        if '/' in ipstr:
            self.ip, self.prefixLen = ipstr.split( '/' )
            return self.ifconfig( ipstr, 'up' )
        else:
            if prefixLen is None:
                raise Exception( 'No prefix length set for IP address %s'
                                 % ( ipstr, ) )
            self.ip, self.prefixLen = ipstr, prefixLen
            return self.ifconfig( '%s/%s' % ( ipstr, prefixLen ) )

    def setMAC( self, macstr ):
        """Set the MAC address for an interface.
           macstr: MAC address as string"""
        self.mac = macstr
        return ( self.ifconfig( 'down' ) +
                 self.ifconfig( 'hw', 'ether', macstr ) +
                 self.ifconfig( 'up' ) )

    _ipMatchRegex = re.compile( r'\d+\.\d+\.\d+\.\d+' )
    _macMatchRegex = re.compile( r'..:..:..:..:..:..' )

    def updateIP( self ):
        "Return updated IP address based on ifconfig"
        # use pexec instead of node.cmd so that we dont read
        # backgrounded output from the cli.
        ifconfig, _err, _exitCode = self.node.pexec(
            'ifconfig %s' % self.name )
        ips = self._ipMatchRegex.findall( ifconfig )
        self.ip = ips[ 0 ] if ips else None
        return self.ip

    def updateMAC( self ):
        "Return updated MAC address based on ifconfig"
        ifconfig = self.ifconfig()
        macs = self._macMatchRegex.findall( ifconfig )
        self.mac = macs[ 0 ] if macs else None
        return self.mac

    # Instead of updating ip and mac separately,
    # use one ifconfig call to do it simultaneously.
    # This saves an ifconfig command, which improves performance.

    def updateAddr( self ):
        "Return IP address and MAC address based on ifconfig."
        ifconfig = self.ifconfig()
        ips = self._ipMatchRegex.findall( ifconfig )
        macs = self._macMatchRegex.findall( ifconfig )
        self.ip = ips[ 0 ] if ips else None
        self.mac = macs[ 0 ] if macs else None
        return self.ip, self.mac

    def IP( self ):
        "Return IP address"
        return self.ip

    def MAC( self ):
        "Return MAC address"
        return self.mac

    def isUp( self, setUp=False ):
        "Return whether interface is up"
        if setUp:
            cmdOutput = self.ifconfig( 'up' )
            # no output indicates success
            if cmdOutput:
                error( "Error setting %s up: %s " % ( self.name, cmdOutput ) )
                return False
            else:
                return True
        else:
            return "UP" in self.ifconfig()

    def rename( self, newname ):
        "Rename interface"
        self.ifconfig( 'down' )
        result = self.cmd( 'ip link set', self.name, 'name', newname )
        self.name = newname
        self.ifconfig( 'up' )
        return result

    # The reason why we configure things in this way is so
    # That the parameters can be listed and documented in
    # the config method.
    # Dealing with subclasses and superclasses is slightly
    # annoying, but at least the information is there!

    def setParam( self, results, method, **param ):
        """Internal method: configure a *single* parameter
           results: dict of results to update
           method: config method name
           param: arg=value (ignore if value=None)
           value may also be list or dict"""
        name, value = param.items()[ 0 ]
        f = getattr( self, method, None )
        if not f or value is None:
            return
        if isinstance( value, list ):
            result = f( *value )
        elif isinstance( value, dict ):
            result = f( **value )
        else:
            result = f( value )
        results[ name ] = result
        return result

    def config( self, mac=None, ip=None, ifconfig=None,
                up=True, **_params ):
        """Configure Node according to (optional) parameters:
           mac: MAC address
           ip: IP address
           ifconfig: arbitrary interface configuration
           Subclasses should override this method and call
           the parent class's config(**params)"""
        # If we were overriding this method, we would call
        # the superclass config method here as follows:
        # r = Parent.config( **params )
        r = {}
        self.setParam( r, 'setMAC', mac=mac )
        self.setParam( r, 'setIP', ip=ip )
        self.setParam( r, 'isUp', up=up )
        self.setParam( r, 'ifconfig', ifconfig=ifconfig )
        return r

    def delete( self ):
        "Delete interface"
        self.cmd( 'ip link del ' + self.name )
        # We used to do this, but it slows us down:
        # if self.node.inNamespace:
        # Link may have been dumped into root NS
        # quietRun( 'ip link del ' + self.name )
        self.node.delIntf( self )
        self.link = None

    def status( self ):
        "Return intf status as a string"
        links, _err, _result = self.node.pexec( 'ip link show' )
        if self.name in links:
            return "OK"
        else:
            return "MISSING"

    def __repr__( self ):
        return '<%s %s>' % ( self.__class__.__name__, self.name )

    def __str__( self ):
        return self.name


class TCIntf( Intf ):
    """Interface customized by tc (traffic control) utility
       Allows specification of bandwidth limits (various methods)
       as well as delay, loss and max queue length"""

    # The parameters we use seem to work reasonably up to 1 Gb/sec
    # For higher data rates, we will probably need to change them.
    bwParamMax = 1000

    def bwCmds( self, bw=None, speedup=0, use_hfsc=False, use_tbf=False,
                latency_ms=None, enable_ecn=False, enable_red=False ):
        "Return tc commands to set bandwidth"

        cmds, parent = [], ' root '

        if bw and ( bw < 0 or bw > self.bwParamMax ):
            error( 'Bandwidth limit', bw, 'is outside supported range 0..%d'
                   % self.bwParamMax, '- ignoring\n' )
        elif bw is not None:
            # BL: this seems a bit brittle...
            if ( speedup > 0 and
                 self.node.name[0:1] == 's' ):
                bw = speedup
            # This may not be correct - we should look more closely
            # at the semantics of burst (and cburst) to make sure we
            # are specifying the correct sizes. For now I have used
            # the same settings we had in the mininet-hifi code.
            if use_hfsc:
                cmds += [ '%s qdisc add dev %s root handle 5:0 hfsc default 1',
                          '%s class add dev %s parent 5:0 classid 5:1 hfsc sc '
                          + 'rate %fMbit ul rate %fMbit' % ( bw, bw ) ]
            elif use_tbf:
                if latency_ms is None:
                    latency_ms = 15 * 8 / bw
                cmds += [ '%s qdisc add dev %s root handle 5: tbf ' +
                          'rate %fMbit burst 15000 latency %fms' %
                          ( bw, latency_ms ) ]
            else:
                cmds += [ '%s qdisc add dev %s root handle 5:0 htb default 1',
                          '%s class add dev %s parent 5:0 classid 5:1 htb ' +
                          'rate %fMbit burst 15k' % bw ]
            parent = ' parent 5:1 '

            # ECN or RED
            if enable_ecn:
                cmds += [ '%s qdisc add dev %s' + parent +
                          'handle 6: red limit 1000000 ' +
                          'min 30000 max 35000 avpkt 1500 ' +
                          'burst 20 ' +
                          'bandwidth %fmbit probability 1 ecn' % bw ]
                parent = ' parent 6: '
            elif enable_red:
                cmds += [ '%s qdisc add dev %s' + parent +
                          'handle 6: red limit 1000000 ' +
                          'min 30000 max 35000 avpkt 1500 ' +
                          'burst 20 ' +
                          'bandwidth %fmbit probability 1' % bw ]
                parent = ' parent 6: '
        return cmds, parent

    @staticmethod
    def delayCmds( parent, delay=None, jitter=None,
                   loss=None, max_queue_size=None ):
        "Internal method: return tc commands for delay and loss"
        cmds = []
        if delay and delay < 0:
            error( 'Negative delay', delay, '\n' )
        elif jitter and jitter < 0:
            error( 'Negative jitter', jitter, '\n' )
        elif loss and ( loss < 0 or loss > 100 ):
            error( 'Bad loss percentage', loss, '%%\n' )
        else:
            # Delay/jitter/loss/max queue size
            netemargs = '%s%s%s%s' % (
                'delay %s ' % delay if delay is not None else '',
                '%s ' % jitter if jitter is not None else '',
                'loss %.5f ' % loss if loss is not None else '',
                'limit %d' % max_queue_size if max_queue_size is not None
                else '' )
            if netemargs:
                cmds = [ '%s qdisc add dev %s ' + parent +
                         ' handle 10: netem ' +
                         netemargs ]
                parent = ' parent 10:1 '
        return cmds, parent

    def tc( self, cmd, tc='tc' ):
        "Execute tc command for our interface"
        c = cmd % (tc, self)  # Add in tc command and our name
        debug(" *** executing command: %s\n" % c)
        return self.cmd( c )

    def config( self, bw=None, delay=None, jitter=None, loss=None,
                gro=False, txo=True, rxo=True,
                speedup=0, use_hfsc=False, use_tbf=False,
                latency_ms=None, enable_ecn=False, enable_red=False,
                max_queue_size=None, **params ):
        """Configure the port and set its properties.
           bw: bandwidth in b/s (e.g. '10m')
           delay: transmit delay (e.g. '1ms' )
           jitter: jitter (e.g. '1ms')
           loss: loss (e.g. '1%' )
           gro: enable GRO (False)
           txo: enable transmit checksum offload (True)
           rxo: enable receive checksum offload (True)
           speedup: experimental switch-side bw option
           use_hfsc: use HFSC scheduling
           use_tbf: use TBF scheduling
           latency_ms: TBF latency parameter
           enable_ecn: enable ECN (False)
           enable_red: enable RED (False)
           max_queue_size: queue limit parameter for netem"""

        # Support old names for parameters
        gro = not params.pop( 'disable_gro', not gro )

        result = Intf.config( self, **params)

        def on( isOn ):
            "Helper method: bool -> 'on'/'off'"
            return 'on' if isOn else 'off'

        # Set offload parameters with ethool
        self.cmd( 'ethtool -K', self,
                  'gro', on( gro ),
                  'tx', on( txo ),
                  'rx', on( rxo ) )

        # Optimization: return if nothing else to configure
        # Question: what happens if we want to reset things?
        if ( bw is None and not delay and not loss
             and max_queue_size is None ):
            return

        # Clear existing configuration
        tcoutput = self.tc( '%s qdisc show dev %s' )
        if "priomap" not in tcoutput and "noqueue" not in tcoutput:
            cmds = [ '%s qdisc del dev %s root' ]
        else:
            cmds = []

        # Bandwidth limits via various methods
        bwcmds, parent = self.bwCmds( bw=bw, speedup=speedup,
                                      use_hfsc=use_hfsc, use_tbf=use_tbf,
                                      latency_ms=latency_ms,
                                      enable_ecn=enable_ecn,
                                      enable_red=enable_red )
        cmds += bwcmds

        # Delay/jitter/loss/max_queue_size using netem
        delaycmds, parent = self.delayCmds( delay=delay, jitter=jitter,
                                            loss=loss,
                                            max_queue_size=max_queue_size,
                                            parent=parent )
        cmds += delaycmds

        # Ugly but functional: display configuration info
        stuff = ( ( [ '%.2fMbit' % bw ] if bw is not None else [] ) +
                  ( [ '%s delay' % delay ] if delay is not None else [] ) +
                  ( [ '%s jitter' % jitter ] if jitter is not None else [] ) +
                  ( ['%.5f%% loss' % loss ] if loss is not None else [] ) +
                  ( [ 'ECN' ] if enable_ecn else [ 'RED' ]
                    if enable_red else [] ) )
        info( '(' + ' '.join( stuff ) + ') ' )

        # Execute all the commands in our node
        debug("at map stage w/cmds: %s\n" % cmds)
        tcoutputs = [ self.tc(cmd) for cmd in cmds ]
        for output in tcoutputs:
            if output != '':
                error( "*** Error: %s" % output )
        debug( "cmds:", cmds, '\n' )
        debug( "outputs:", tcoutputs, '\n' )
        result[ 'tcoutputs'] = tcoutputs
        result[ 'parent' ] = parent

        return result


class Link( object ):

    """A basic link is just a veth pair.
       Other types of links could be tunnels, link emulators, etc.."""

    # pylint: disable=too-many-branches
    def __init__( self, node1, node2, port1=None, port2=None,
                  intfName1=None, intfName2=None, addr1=None, addr2=None,
                  intf=Intf, cls1=None, cls2=None, params1=None,
                  params2=None, fast=True ):
        """Create veth link to another node, making two new interfaces.
           node1: first node
           node2: second node
           port1: node1 port number (optional)
           port2: node2 port number (optional)
           intf: default interface class/constructor
           cls1, cls2: optional interface-specific constructors
           intfName1: node1 interface name (optional)
           intfName2: node2  interface name (optional)
           params1: parameters for interface 1
           params2: parameters for interface 2"""
        # This is a bit awkward; it seems that having everything in
        # params is more orthogonal, but being able to specify
        # in-line arguments is more convenient! So we support both.
        if params1 is None:
            params1 = {}
        if params2 is None:
            params2 = {}
        # Allow passing in params1=params2
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

        # All we are is dust in the wind, and our two interfaces
        self.intf1, self.intf2 = intf1, intf2
    # pylint: enable=too-many-branches

    @staticmethod
    def _ignore( *args, **kwargs ):
        "Ignore any arguments"
        pass

    def intfName( self, node, n ):
        "Construct a canonical interface name node-ethN for interface n."
        # Leave this as an instance method for now
        assert self
        return node.name + '-eth' + repr( n )

    @classmethod
    def makeIntfPair( cls, intfname1, intfname2, addr1=None, addr2=None,
                      node1=None, node2=None, deleteIntfs=True ):
        """Create pair of interfaces
           intfname1: name for interface 1
           intfname2: name for interface 2
           addr1: MAC address for interface 1 (optional)
           addr2: MAC address for interface 2 (optional)
           node1: home node for interface 1 (optional)
           node2: home node for interface 2 (optional)
           (override this method [and possibly delete()]
           to change link type)"""
        # Leave this as a class method for now
        assert cls
        return makeIntfPair( intfname1, intfname2, addr1, addr2, node1, node2,
                             deleteIntfs=deleteIntfs )

    def delete( self ):
        "Delete this link"
        self.intf1.delete()
        self.intf1 = None
        self.intf2.delete()
        self.intf2 = None

    def stop( self ):
        "Override to stop and clean up link as needed"
        self.delete()

    def status( self ):
        "Return link status as a string"
        return "(%s %s)" % ( self.intf1.status(), self.intf2.status() )

    def __str__( self ):
        return '%s<->%s' % ( self.intf1, self.intf2 )


class OVSIntf( Intf ):
    "Patch interface on an OVSSwitch"

    def ifconfig( self, *args ):
        cmd = ' '.join( args )
        if cmd == 'up':
            # OVSIntf is always up
            return
        else:
            raise Exception( 'OVSIntf cannot do ifconfig ' + cmd )


class OVSLink( Link ):
    """Link that makes patch links between OVSSwitches
       Warning: in testing we have found that no more
       than ~64 OVS patch links should be used in row."""

    def __init__( self, node1, node2, **kwargs ):
        from mininet.node import OVSSwitch

        "See Link.__init__() for options"
        self.isPatchLink = False
        if ( isinstance( node1, OVSSwitch ) and
             isinstance( node2, OVSSwitch ) ):
            self.isPatchLink = True
            kwargs.update( cls1=OVSIntf, cls2=OVSIntf )
        Link.__init__( self, node1, node2, **kwargs )

    def makeIntfPair( self, *args, **kwargs ):
        "Usually delegated to OVSSwitch"
        if self.isPatchLink:
            return None, None
        else:
            return Link.makeIntfPair( *args, **kwargs )


class TCLink( Link ):
    "Link with symmetric TC interfaces configured via opts"
    def __init__( self, node1, node2, port1=None, port2=None,
                  intfName1=None, intfName2=None,
                  addr1=None, addr2=None, **params ):
        Link.__init__( self, node1, node2, port1=port1, port2=port2,
                       intfName1=intfName1, intfName2=intfName2,
                       cls1=TCIntf,
                       cls2=TCIntf,
                       addr1=addr1, addr2=addr2,
                       params1=params,
                       params2=params )


class TCULink( TCLink ):
    """TCLink with default settings optimized for UserSwitch
       (txo=rxo=0/False).  Unfortunately with recent Linux kernels,
       enabling TX and RX checksum offload on veth pairs doesn't work
       well with UserSwitch: either it gets terrible performance or
       TCP packets with bad checksums are generated, forwarded, and
       *dropped* due to having bad checksums! OVS and LinuxBridge seem
       to cope with this somehow, but it is likely to be an issue with
       many software Ethernet bridges."""

    def __init__( self, *args, **kwargs ):
        kwargs.update( txo=False, rxo=False )
        TCLink.__init__( self, *args, **kwargs )
