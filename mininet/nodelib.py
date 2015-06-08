"""
Node Library for Mininet

This contains additional Node types which you may find to be useful.
"""

from mininet.node import Node, Host, Switch
from mininet.log import info, warn
from mininet.moduledeps import pathCheck
from mininet.util import quietRun

import re
from tempfile import NamedTemporaryFile

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

    def start( self, _controllers ):
        "Start Linux bridge"
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

    def stop( self, deleteIntfs=True ):
        """Stop Linux bridge
           deleteIntfs: delete interfaces? (True)"""
        self.cmd( 'ifconfig', self, 'down' )
        self.cmd( 'brctl delbr', self )
        super( LinuxBridge, self ).stop( deleteIntfs )

    def dpctl( self, *args ):
        "Run brctl command"
        return self.cmd( 'brctl', *args )

    @classmethod
    def setup( cls ):
        "Check dependencies and warn about firewalling"
        pathCheck( 'brctl', moduleName='bridge-utils' )
        # Disable Linux bridge firewalling so that traffic can flow!
        for table in 'arp', 'ip', 'ip6':
            cmd = 'sysctl net.bridge.bridge-nf-call-%stables' % table
            out = quietRun( cmd ).strip()
            if out.endswith( '1' ):
                warn( 'Warning: Linux bridge may not work with', out, '\n' )


class NAT( Node ):
    "NAT: Provides connectivity to external network"

    def __init__( self, name, subnet='10.0/8',
                  localIntf=None, flush=False, **params):
        """Start NAT/forwarding between Mininet and external network
           subnet: Mininet subnet (default 10.0/8)
           flush: flush iptables before installing NAT rules"""
        super( NAT, self ).__init__( name, **params )

        self.subnet = subnet
        self.localIntf = localIntf
        self.flush = flush
        self.forwardState = self.cmd( 'sysctl -n net.ipv4.ip_forward' ).strip()

    def config( self, **params ):
        """Configure the NAT and iptables"""
        super( NAT, self).config( **params )

        if not self.localIntf:
            self.localIntf = self.defaultIntf()

        if self.flush:
            self.cmd( 'sysctl net.ipv4.ip_forward=0' )
            self.cmd( 'iptables -F' )
            self.cmd( 'iptables -t nat -F' )
            # Create default entries for unmatched traffic
            self.cmd( 'iptables -P INPUT ACCEPT' )
            self.cmd( 'iptables -P OUTPUT ACCEPT' )
            self.cmd( 'iptables -P FORWARD DROP' )

        # Install NAT rules
        self.cmd( 'iptables -I FORWARD',
                  '-i', self.localIntf, '-d', self.subnet, '-j DROP' )
        self.cmd( 'iptables -A FORWARD',
                  '-i', self.localIntf, '-s', self.subnet, '-j ACCEPT' )
        self.cmd( 'iptables -A FORWARD',
                  '-o', self.localIntf, '-d', self.subnet,'-j ACCEPT' )
        self.cmd( 'iptables -t nat -A POSTROUTING',
                  '-s', self.subnet, "'!'", '-d', self.subnet, '-j MASQUERADE' )

        # Instruct the kernel to perform forwarding
        self.cmd( 'sysctl net.ipv4.ip_forward=1' )

        # Prevent network-manager from messing with our interface
        # by specifying manual configuration in /etc/network/interfaces
        intf = self.localIntf
        cfile = '/etc/network/interfaces'
        line = '\niface %s inet manual\n' % intf
        config = open( cfile ).read()
        if ( line ) not in config:
            info( '*** Adding "' + line.strip() + '" to ' + cfile + '\n' )
            with open( cfile, 'a' ) as f:
                f.write( line )
        # Probably need to restart network-manager to be safe -
        # hopefully this won't disconnect you
        self.cmd( 'service network-manager restart' )

    def terminate( self ):
        "Stop NAT/forwarding between Mininet and external network"
        # Remote NAT rules
        self.cmd( 'iptables -D FORWARD',
                   '-i', self.localIntf, '-d', self.subnet, '-j DROP' )
        self.cmd( 'iptables -D FORWARD',
                  '-i', self.localIntf, '-s', self.subnet, '-j ACCEPT' )
        self.cmd( 'iptables -D FORWARD',
                  '-o', self.localIntf, '-d', self.subnet,'-j ACCEPT' )
        self.cmd( 'iptables -t nat -D POSTROUTING',
                  '-s', self.subnet, '\'!\'', '-d', self.subnet, '-j MASQUERADE' )
        # Put the forwarding state back to what it was
        self.cmd( 'sysctl net.ipv4.ip_forward=%s' % self.forwardState )
        super( NAT, self ).terminate()

class Server( Host ):
    """Run sshd in a net/mnt/pid/uts namespace, with private /etc/hosts
       WARNING!!! KNOWN ISSUES:
       - control-c does not work in Mininet CLI with pid namespace
       - xterm does not work from Mininet CLI
       We may be able to address these issues in the future."""
    
    inNamespace = [ 'net', 'mnt', 'pid', 'uts' ]
    overlayDirs = [ '/etc', '/var/run', '/var/log' ]
    privateDirs = [ '/var/run/sshd' ]

    def __init__( self, *args, **kwargs ):
        """Add overlay dirs and private dirs, and change permissions
           ssh: run sshd? (True)"""
        kwargs.setdefault( 'ssh', True )
        kwargs.setdefault( 'inNamespace', self.inNamespace )
        kwargs.setdefault( 'privateDirs', self.privateDirs )
        kwargs.setdefault( 'overlayDirs', self.overlayDirs )
        super( Server, self ).__init__( *args, **kwargs )
        # Change permissions, mainly for ssh
        for pdir in self.privateDirs:
            self.cmd( 'chown root:root', pdir )
            self.cmd( 'chmod 755', pdir )

    @staticmethod
    def updateHostsFiles( servers, tmpdir='/tmp' ):
        """Update local hosts files on a list of servers
            servers: list of servers
            tmpdir: tmp dir shared between mn and servers"""
        # This scales as n^2, so for a large configuration it's
        # more efficient to use a DNS server
        for s in servers:
            dirs = ( getattr( s, 'overlayDirs', [] ) +
            getattr( s, 'privateDirs', [] ))
            if '/etc' in dirs:
                with NamedTemporaryFile( dir=tmpdir ) as tmpfile:
                      tmpfile.write( '# Mininet hosts file\n' )
                      tmpfile.write( '127.0.0.1 localhost %s\n' % s )
                      for t  in servers:
                        tmpfile.write( '%s %s\n' % ( t.IP(), t ) )
                      tmpfile.flush()
                      s.cmd( 'cp', tmpfile.name, '/etc/hosts' )
            else:
                warn( 'not updating hosts file on %s\n' % s )

    def service( self, cmd ):
        """Start or stop a service
           usage: service( 'ssh stop' )"""
        self.cmd( '/etc/init.d/%s' % cmd )

    def motd( self ):
        "Return login message as a string"
        return 'Welcome to Mininet host %s at %s' % ( self, self.IP() )

    def startSSH( self, motdPath='/var/run/motd.dynamic' ):
        "Update motd, clear out utmp/wtmp/btmp, and start sshd"
        # Note: /var/run and /var/log must be overlays!
        assert ( '/var/run' in ( self.overlayDirs + self.privateDirs ) and
                 '/var/log' in ( self.overlayDirs + self.privateDirs ) )
        self.cmd( "echo  '%s' > %s" % ( self.motd(), motdPath ) )
        self.cmd( 'truncate -s0 /var/run/utmp /var/log/wtmp* /var/log/btmp*' )
        # sshd.pid should really be in /var/run/sshd instead of /var/run
        self.cmd( 'rm /var/run/sshd.pid' )
        self.cmd( '/etc/init.d/ssh start' )
    
    def config( self, **kwargs ):
        """Configure/start sshd and other stuff
            ssh: start sshd? (True )"""
        super( Server, self ).config( **kwargs )
        self.ssh = kwargs.get( 'ssh' )
        if self.ssh:
            self.startSSH()
        if 'uts' in self.inNamespace:
            self.cmd( 'hostname', self )
    
    def terminate( self, *args, **kwargs ):
        "Shut down services and terminate server"
        if self.ssh:
            self.service( 'ssh stop' )
        super( Server, self ).terminate( *args, **kwargs )


