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
        self.config( **kwargs )

    def cmd( self, *args, **kwargs ):
        self.node.cmd( *args, **kwargs )

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


    # Map of config params to config methods
    # Perhaps this could be more graceful, but it
    # is flexible
    configMap = { 'mac': 'setMAC', 
                  'ip': 'setIP',
                  'ifconfig': 'ifconfig' }

    def config( self, **params ):
        "Configure interface based on parameters"
        self.__dict__.update(**params)
        for name, value in params.iteritems():
            method = self.configMap.get( name, None )
            if method:
                if type( value ) is str:
                    value = value.split( ',' )
                method( value )

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
                enable_red=False, max_queue_size=1000, **kwargs ):
        "Configure the port and set its properties."

        BasicIntf.config( self, **kwargs)

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
            info( self, '(bw %.2fMbit, delay %s, loss %d%%)\n' % 
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
        
        outputs = [ doConfigPort(cmd) for cmd in cmds ]
        debug( "outputs: %s\n" % outputs )

Intf = TCIntf

class Link( object ):
    
    """A basic link is just a veth pair.
       Other types of links could be tunnels, link emulators, etc.."""

    def __init__( self, node1, node2, port1=None, port2=None, intfName1=None, intfName2=None,
                  intf=Intf, params1={}, params2={} ):
        """Create veth link to another node, making two new interfaces.
           node1: first node
           node2: second node
           port1: node1 port number (optional)
           port2: node2 port number (optional)
           intfName1: node1 interface name (optional)
           intfName2: node2  interface name (optional)"""
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
        intf1 = intf( name=intfName1, node=node1, link=self, **params1  )
        intf2 = intf( name=intfName2, node=node2, link=self, **params2 )
        # Add to nodes
        node1.addIntf( intf1 )
        node2.addIntf( intf2 )
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




    

