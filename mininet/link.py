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

"""

from mininet.log import info, error, debug
from mininet.util import makeIntfPair
from time import sleep
import re

class BasicIntf( object ):

    "Basic interface object that can configure itself."

    def __init__( self, node, name=None, link=None, **kwargs ):
        """node: owning node (where this intf most likely lives)
           name: interface name (e.g. h1-eth0)
           link: parent link if any
           other arguments are used to configure link parameters"""
        self.node = node
        self.name = name
        self.link = link
        self.mac, self.ip = None, None
        # Add to node (and move ourselves if necessary )
        node.addIntf( self )
        self.config( **kwargs )

    def cmd( self, *args, **kwargs ):
        return self.node.cmd( *args, **kwargs )

    def ifconfig( self, *args ):
        "Configure ourselves using ifconfig"
        return self.cmd( 'ifconfig', self.name, *args )

    def setIP( self, ipstr ):
        """Set our IP address"""
        # This is a sign that we should perhaps rethink our prefix
        # mechanism
        self.ip, self.prefixLen = ipstr.split( '/' )
        return self.ifconfig( ipstr, 'up' )

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

    def updateMAC( self, intf ):
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

    def isUp( self, set=False ):
        "Return whether interface is up"
        return "UP" in self.ifconfig()

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
                defaultRoute=None, **params):
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
        self.setParam( r, 'ifconfig', ifconfig=ifconfig )
        return r

    def delete( self ):
        "Delete interface"
        self.cmd( 'ip link del ' + self.name )
        # Does it help to sleep to let things run?
        sleep( 0.001 )

    def __str__( self ):
        return self.name


class TCIntf( BasicIntf ):
    "Interface customized by tc (traffic control) utility"  

    def config( self, bw=None, delay=None, loss=0, disable_gro=True,
                speedup=0, use_hfsc=False, use_tbf=False, enable_ecn=False,
                enable_red=False, max_queue_size=1000, **params ):
        "Configure the port and set its properties."

        result = BasicIntf.config( self, **params)

        # disable GRO
        if disable_gro:
            self.cmd( 'ethtool -K %s gro off' % self )
        
        if bw is None and not delay and not loss:
            return

        if bw and ( bw < 0 or bw > 1000 ):
            error( 'Bandwidth', bw, 'is outside range 0..1000 Mbps\n' )
            return
            
        if delay and delay < 0:
            error( 'Negative delay', delay, '\n' )
            return

        if loss and ( loss < 0 or loss > 100 ):
            error( 'Bad loss percentage', loss, '%%\n' )
            return
        
        if delay is None:
            delay = '0ms'
        
        if bw is not None and delay is not None:
            info( self, '(bw %.2fMbit, delay %s, loss %d%%) ' % 
                 ( bw, delay, loss ) )
        
        # BL: hmm... what exactly is this???
        # This seems kind of brittle
        if speedup > 0 and self.node.name[0:2] == 'sw':
            bw = speedup

        tc = 'tc' # was getCmd( 'tc' )

        # Bandwidth control algorithms
        if use_hfsc:
            cmds = [ '%s qdisc del dev %s root',
                     '%s qdisc add dev %s root handle 1:0 hfsc default 1' ]
            if bw is not None:
                cmds.append( '%s class add dev %s parent 1:0 classid 1:1 hfsc sc ' +
                            'rate %fMbit ul rate %fMbit' % ( bw, bw ) )
        elif use_tbf:
            latency_us = 10 * 1500 * 8 / bw
            cmds = ['%s qdisc del dev %s root',
                    '%s qdisc add dev %s root handle 1: tbf ' +
                    'rate %fMbit burst 15000 latency %fus' % (bw, latency_us) ]
        else:
            cmds = [ '%s qdisc del dev %s root',
                     '%s qdisc add dev %s root handle 1:0 htb default 1',
                     '%s class add dev %s parent 1:0 classid 1:1 htb ' +
                     'rate %fMbit burst 15k' % bw ]

        # ECN or RED
        if enable_ecn:
            info( 'Enabling ECN\n' )
            cmds += [ '%s qdisc add dev %s parent 1:1 '+
                      'handle 10: red limit 1000000 '+
                      'min 20000 max 25000 avpkt 1000 '+
                      'burst 20 '+
                      'bandwidth %fmbit probability 1 ecn' % bw ]
        elif enable_red:
            info( 'Enabling RED\n' )
            cmds += [ '%s qdisc add dev %s parent 1:1 '+
                      'handle 10: red limit 1000000 '+
                      'min 20000 max 25000 avpkt 1000 '+
                      'burst 20 '+
                      'bandwidth %fmbit probability 1' % bw ]
        else:
            cmds += [ '%s qdisc add dev %s parent 1:1 handle 10:0 netem ' +
                     'delay ' + '%s' % delay + ' loss ' + '%d' % loss + 
                     ' limit %d' % (max_queue_size) ]
        
        # Execute all the commands in the container
        debug("at map stage w/cmds: %s\n" % cmds)
        
        def doConfigPort(s):
            c = s % (tc, self)
            debug(" *** executing command: %s\n" % c)
            return self.cmd(c)
        
        tcoutputs = [ doConfigPort(cmd) for cmd in cmds ]
        debug( "cmds:", cmds, '\n' )
        debug( "outputs:", tcoutputs, '\n' )
        result[ 'tcoutputs'] = tcoutputs
        return result

Intf = TCIntf

class Link( object ):
    
    """A basic link is just a veth pair.
       Other types of links could be tunnels, link emulators, etc.."""

    def __init__( self, node1, node2, port1=None, port2=None, intfName1=None, intfName2=None,
                  intf=Intf, cls1=None, cls2=None, params1={}, params2={} ):
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
        intf1 = cls1( name=intfName1, node=node1, link=self, **params1  )
        intf2 = cls2( name=intfName2, node=node2, link=self, **params2 )
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
           (override this class method [and possibly delete()] to change link type)"""
        makeIntfPair( intf1, intf2  )

    def delete( self ):
        "Delete this link"
        self.intf1.delete()
        self.intf2.delete()

    def __str__( self ):
        return '%s<->%s' % ( self.intf1, self.intf2 )
