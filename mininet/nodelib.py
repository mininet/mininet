"""
Node Library for Mininet

This contains additional Node types which you may find to be useful.
"""

from mininet.node import Node, Switch
from mininet.log import setLogLevel, info

class LinuxBridge( Switch ):
    "Linux Bridge (with optional spanning tree)"

    nextPrio = 100  # next bridge priority for spanning tree

    def __init__( self, name, stp=False, prio=None, **kwargs ):
        """stp: use spanning tree protocol? (default False)
           prio: optional explicit bridge priority for STP"""
        self.stp = stp
        if prio:
            self.prio = prio
        else:
            self.prio = LinuxBridge.nextPrio
            LinuxBridge.nextPrio += 1
        Switch.__init__( self, name, **kwargs )

    def connected( self ):
        "Are we forwarding yet?"
        if self.stp:
            return 'forwarding' in self.cmd( 'brctl showstp', self )
        else:
            return True
    
    def start( self, controllers ):
        self.cmd( 'ifconfig', self, 'down' )
        self.cmd( 'brctl delbr', self )
        self.cmd( 'brctl addbr', self )
        if self.stp:
            self.cmd( 'brctl setbridgeprio', self.prio )
            self.cmd( 'brctl stp', self, 'on' )
        for i in self.intfList():
            if self.name in i.name:
                self.cmd( 'brctl addif', self, i )
        self.cmd( 'ifconfig', self, 'up' )

    def stop( self ):
        self.cmd( 'ifconfig', self, 'down' )
        self.cmd( 'brctl delbr', self )

class NAT( Node ):
    """NAT: Provides connectivity to external network"""

    def __init__( self, name, inetIntf='eth0', subnet='10.0/8', localIntf=None, **params):
        super( NAT, self ).__init__( name, **params )

        """Start NAT/forwarding between Mininet and external network
        inetIntf: interface for internet access
        subnet: Mininet subnet (default 10.0/8)="""
        self.inetIntf = inetIntf
        self.subnet = subnet
        self.localIntf = localIntf

    def config( self, **params ):
        super( NAT, self).config( **params )
        """Configure the NAT and iptables"""

        if not self.localIntf:
            self.localIntf =  self.defaultIntf()

        self.cmd( 'sysctl net.ipv4.ip_forward=0' )

        # Flush any currently active rules
        # TODO: is this safe?
        self.cmd( 'iptables -F' )
        self.cmd( 'iptables -t nat -F' )

        # Create default entries for unmatched traffic
        self.cmd( 'iptables -P INPUT ACCEPT' )
        self.cmd( 'iptables -P OUTPUT ACCEPT' )
        self.cmd( 'iptables -P FORWARD DROP' )

        # Configure NAT
        self.cmd( 'iptables -I FORWARD -i', self.localIntf, '-d', self.subnet, '-j DROP' )
        self.cmd( 'iptables -A FORWARD -i', self.localIntf, '-s', self.subnet, '-j ACCEPT' )
        self.cmd( 'iptables -A FORWARD -i', self.inetIntf, '-d', self.subnet, '-j ACCEPT' )
        self.cmd( 'iptables -t nat -A POSTROUTING -o ', self.inetIntf, '-j MASQUERADE' )

        # Instruct the kernel to perform forwarding
        self.cmd( 'sysctl net.ipv4.ip_forward=1' )

        # Prevent network-manager from messing with our interface
        # by specifying manual configuration in /etc/network/interfaces
        intf = self.localIntf
        cfile = '/etc/network/interfaces'
        line = '\niface %s inet manual\n' % intf
        config = open( cfile ).read()
        if ( line ) not in config:
            info( '*** Adding "' + line.strip() + '" to ' + cfile )
            with open( cfile, 'a' ) as f:
                f.write( line )
        # Probably need to restart network-manager to be safe -
        # hopefully this won't disconnect you
        self.cmd( 'service network-manager restart' )

    def terminate( self ):
        """Stop NAT/forwarding between Mininet and external network"""
        # Flush any currently active rules
        # TODO: is this safe?
        self.cmd( 'iptables -F' )
        self.cmd( 'iptables -t nat -F' )

        # Instruct the kernel to stop forwarding
        self.cmd( 'sysctl net.ipv4.ip_forward=0' )

        super( NAT, self ).terminate()

