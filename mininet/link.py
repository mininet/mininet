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
from time import sleep
import re

class Intf( object ):

    "Basic interface object that can configure itself."

    def __init__( self, name, node=None, port=None, link=None, **params ):
        """name: interface name (e.g. h1-eth0)
           node: owning node (where this intf most likely lives)
           link: parent link if we're part of a link
           other arguments are passed to config()"""
        self.node = node
        self.name = name
        self.link = link
        self.mac, self.ip, self.prefixLen = None, None, None
        # Add to node (and move ourselves if necessary )
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
        ifconfig = self.ifconfig()
        ips = self._ipMatchRegex.findall( ifconfig )
        self.ip = ips[ 0 ] if ips else None
        return self.ip

    def updateMAC( self ):
        "Return updated MAC address based on ifconfig"
        ifconfig = self.ifconfig()
        macs = self._macMatchRegex.findall( ifconfig )
        self.mac = macs[ 0 ] if macs else None
        return self.mac

    def IP( self ):
        "Return IP address"
        return self.ip

    def MAC( self ):
        "Return MAC address"
        return self.mac

    def isUp( self, setUp=False ):
        "Return whether interface is up"
        if setUp:
            self.ifconfig( 'up' )
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
        if type( value ) is list:
            result = f( *value )
        elif type( value ) is dict:
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
        self.updateIP()
        self.updateMAC()
        return r

    def delete( self ):
        "Delete interface"
        self.cmd( 'ip link del ' + self.name )
        # Does it help to sleep to let things run?
        sleep( 0.001 )

    def __repr__( self ):
        return '<%s %s>' % ( self.__class__.__name__, self.name )

    def __str__( self ):
        return self.name


class TCIntf( Intf ):
    """Interface customized by tc (traffic control) utility
       Allows specification of bandwidth limits (various methods)
       as well as delay, loss and max queue length"""

    def bwCmds( self, bw=None, speedup=0, use_hfsc=False, use_tbf=False,
                latency_ms=None, enable_ecn=False, enable_red=False ):
        "Return tc commands to set bandwidth"

        cmds, parent = [], ' root '

        if bw and ( bw < 0 or bw > 1000 ):
            error( 'Bandwidth', bw, 'is outside range 0..1000 Mbps\n' )

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
                cmds += [ '%s qdisc add dev %s root handle 1:0 hfsc default 1',
                          '%s class add dev %s parent 1:0 classid 1:1 hfsc sc '
                          + 'rate %fMbit ul rate %fMbit' % ( bw, bw ) ]
            elif use_tbf:
                if latency_ms is None:
                    latency_ms = 15 * 8 / bw
                cmds += [ '%s qdisc add dev %s root handle 1: tbf ' +
                          'rate %fMbit burst 15000 latency %fms' %
                          ( bw, latency_ms ) ]
            else:
                cmds += [ '%s qdisc add dev %s root handle 1:0 htb default 1',
                          '%s class add dev %s parent 1:0 classid 1:1 htb ' +
                          'rate %fMbit burst 15k' % bw ]
            parent = ' parent 1:1 '

            # ECN or RED
            if enable_ecn:
                cmds += [ '%s qdisc add dev %s' + parent +
                          'handle 10: red limit 1000000 ' +
                          'min 30000 max 35000 avpkt 1500 ' +
                          'burst 20 ' +
                          'bandwidth %fmbit probability 1 ecn' % bw ]
                parent = ' parent 10: '
            elif enable_red:
                cmds += [ '%s qdisc add dev %s' + parent +
                          'handle 10: red limit 1000000 ' +
                          'min 30000 max 35000 avpkt 1500 ' +
                          'burst 20 ' +
                          'bandwidth %fmbit probability 1' % bw ]
                parent = ' parent 10: '
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
                'loss %d ' % loss if loss is not None else '',
                'limit %d' % max_queue_size if max_queue_size is not None
                else '' )
            if netemargs:
                cmds = [ '%s qdisc add dev %s ' + parent +
                         ' handle 10: netem ' +
                         netemargs ]
        return cmds

    def tc( self, cmd, tc='tc' ):
        "Execute tc command for our interface"
        c = cmd % (tc, self)  # Add in tc command and our name
        debug(" *** executing command: %s\n" % c)
        return self.cmd( c )

    def config( self, bw=None, delay=None, jitter=None, loss=None,
                disable_gro=True, speedup=0, use_hfsc=False, use_tbf=False,
                latency_ms=None, enable_ecn=False, enable_red=False,
                max_queue_size=None, **params ):
        "Configure the port and set its properties."

        result = Intf.config( self, **params)

        # Disable GRO
        if disable_gro:
            self.cmd( 'ethtool -K %s gro off' % self )

        # Optimization: return if nothing else to configure
        # Question: what happens if we want to reset things?
        if ( bw is None and not delay and not loss
             and max_queue_size is None ):
            return

        # Clear existing configuration
        cmds = [ '%s qdisc del dev %s root' ]

        # Bandwidth limits via various methods
        bwcmds, parent = self.bwCmds( bw=bw, speedup=speedup,
                                      use_hfsc=use_hfsc, use_tbf=use_tbf,
                                      latency_ms=latency_ms,
                                      enable_ecn=enable_ecn,
                                      enable_red=enable_red )
        cmds += bwcmds

        # Delay/jitter/loss/max_queue_size using netem
        cmds += self.delayCmds( delay=delay, jitter=jitter, loss=loss,
                                max_queue_size=max_queue_size,
                                parent=parent )

        # Ugly but functional: display configuration info
        stuff = ( ( [ '%.2fMbit' % bw ] if bw is not None else [] ) +
                  ( [ '%s delay' % delay ] if delay is not None else [] ) +
                  ( [ '%s jitter' % jitter ] if jitter is not None else [] ) +
                  ( ['%d%% loss' % loss ] if loss is not None else [] ) +
                  ( [ 'ECN' ] if enable_ecn else [ 'RED' ]
                    if enable_red else [] ) )
        info( '(' + ' '.join( stuff ) + ') ' )

        # Execute all the commands in our node
        debug("at map stage w/cmds: %s\n" % cmds)
        tcoutputs = [ self.tc(cmd) for cmd in cmds ]
        debug( "cmds:", cmds, '\n' )
        debug( "outputs:", tcoutputs, '\n' )
        result[ 'tcoutputs'] = tcoutputs

        return result


class Link( object ):

    """A basic link is just a veth pair.
       Other types of links could be tunnels, link emulators, etc.."""

    def __init__( self, node1, node2, port1=None, port2=None,
                  intfName1=None, intfName2=None,
                  intf=Intf, cls1=None, cls2=None, params1=None,
                  params2=None ):
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
        # params would be more orthogonal, but being able to specify
        # in-line arguments is more convenient!
        if port1 is None:
            port1 = node1.newPort()
        if port2 is None:
            port2 = node2.newPort()
        if not intfName1:
            intfName1 = self.intfName( node1, port1 )
        if not intfName2:
            intfName2 = self.intfName( node2, port2 )

        self.makeIntfPair( intfName1, intfName2 )

        if not cls1:
            cls1 = intf
        if not cls2:
            cls2 = intf
        if not params1:
            params1 = {}
        if not params2:
            params2 = {}

        intf1 = cls1( name=intfName1, node=node1, port=port1,
                      link=self, **params1  )
        intf2 = cls2( name=intfName2, node=node2, port=port2,
                      link=self, **params2 )

        # All we are is dust in the wind, and our two interfaces
        self.intf1, self.intf2 = intf1, intf2

    @classmethod
    def intfName( cls, node, n ):
        "Construct a canonical interface name node-ethN for interface n."
        return node.name + '-eth' + repr( n )

    @classmethod
    def makeIntfPair( cls, intf1, intf2 ):
        """Create pair of interfaces
           intf1: name of interface 1
           intf2: name of interface 2
           (override this class method [and possibly delete()]
           to change link type)"""
        makeIntfPair( intf1, intf2  )

    def delete( self ):
        "Delete this link"
        self.intf1.delete()
        self.intf2.delete()

    def __str__( self ):
        return '%s<->%s' % ( self.intf1, self.intf2 )

class TCLink( Link ):
    "Link with symmetric TC interfaces configured via opts"
    def __init__( self, node1, node2, port1=None, port2=None,
                  intfName1=None, intfName2=None, **params ):
        Link.__init__( self, node1, node2, port1=port1, port2=port2,
                       intfName1=intfName1, intfName2=intfName2,
                       cls1=TCIntf,
                       cls2=TCIntf,
                       params1=params,
                       params2=params)
