#!/usr/bin/python

"""
fakecluster.py: a fake cluster for testing Mininet cluster edition!!!

We are going to self-host Mininet by creating a virtual cluster
for cluster edition.

Note: ssh is kind of a mess - you end up having to do things
like h1 sudo -E -u openflow ssh 10.2
"""

from mininet.net import Mininet
from mininet.node import Host
from mininet.cli import CLI
from mininet.topo import Topo, SingleSwitchTopo
from mininet.log import setLogLevel
from mininet.util import errRun

from functools import partial

"""
Comments
Next:
- dnsmasq on m1
- custom /etc/resolv.conf pointing to m1 on m1-mn
And maybe:
- dnsmasq on root server
- root resolv.conf pointing to dnsmasq? Hmm...
"""

class Server( Host ):
    "A host that supports overlay directories"

    def __init__( self, *args, **kwargs ):
        "Add private dirs and overlay dirs"
        self.overlayDirs = kwargs.pop( 'overlayDirs', () )
        Host.__init__( self, *args, **kwargs )

    def mountPrivateDirs( self ):
        """Overridden to pre-mount overlay dirs
           Usually there isn't a good reason for them to overlap,
           but if they do, then the private dirs are mounted
           on top of the overlay dirs.
           We also make our private dirs root/755"""
        self.mountOverlayDirs()
        super( Server, self ).mountPrivateDirs()

    def unmountPrivateDirs( self ):
        "Overridden to also unmount overlay dirs"
        super( Server, self).unmountPrivateDirs()
        self.unmountOverlayDirs()

    def _overlayFrom( self, entry ):
        "Helper function: return mountpaint, overlay, tmpfs from entry"
        if type( entry ) is str:
            # '/mountpoint'
            mountpoint, overlay = entry, None
        elif len( entry ) is 1:
            # [ '/mountpoint' ]
            mountpoint, overlay = entry[ 0 ], None
        else:
            # [ '/mountpoint', '/overlay' ]
            mountpoint, overlay = entry
        tmpfs = None if overlay else '/tmp/%s/%s' % ( self, mountpoint )
        return mountpoint, overlay, tmpfs

    def mountOverlayDirs( self ):
        """Mount overlay directories. Overlay directories are similar
           to private directories except they are copy-on-write copies
           of directories in the host file system.
           overlayDirs is of the form ((mountpoint,overlaydir), ...)
           much like privateDirs. If overlaydir doesn't exist, we
           mount a tmpfs at the specified mount point."""
        for entry in self.overlayDirs:
            mountpoint, overlay, tmpfs  = self._overlayFrom( entry )
            # Create tmpfs if overlay dir is not specified
            if not overlay:
                overlay = tmpfs
                self.cmd( 'mkdir -p', overlay )
                self.cmd( 'mount -t tmpfs tmpfs', overlay )
            # Mount overlay dir at mount point
            self.cmd( ( 'mount -t overlayfs -o upperdir=%s,lowerdir=%s'
                        ' overlayfs %s' ) % ( overlay, mountpoint, mountpoint ) )

    def unmountOverlayDirs( self ):
        "Unmount overlay directories"
        for entry in self.overlayDirs:
            mountpoint, overlay, tmpfs = self._overlayFrom( entry )
            # Unfortunately these umounts can fail if the mount point
            # is in use, possibly leaving tmpfs garbage in the root
            # mount namespace / file system
            self.cmd( 'umount', mountpoint )
            if not overlay:
                self.cmd( 'umount', tmpfs )


class MininetServer( Server ):
    "A server (for nested Mininet) that can run ssh and ovsdb"

    overlayDirs = ( '/etc', '/var/run' )
    privateDirs = ( '/var/run/sshd',
                    '/var/run/openvswitch', '/var/log/openvswitch' )

    def __init__( self, *args, **kwargs ):
        "Add overlay dirs and private dirs, and change permissions"
        kwargs.update( overlayDirs=self.overlayDirs,
                       privateDirs=self.privateDirs )
        Host.__init__( self, *args, **kwargs )
        # Change permissions, mainly for ssh
        for pdir in self.privateDirs:
            self.cmd( 'chown root:root', pdir )
            self.cmd( 'chmod 755', pdir )

    def startSSH( self ):
        "Start sshd"
        msg  = '***  Welcome to Mininet host %s at %s' % ( self, self.IP() )
        bfile = '/etc/ssh/ssh_banner'
        self.cmd( 'echo "%s" > %s' % ( msg, bfile ) )
        self.cmd( 'echo "Banner %s" >> /etc/ssh/sshd_config' % bfile )
        # This pid file should really be in /var/run/sshd
        self.cmd( 'rm /var/run/sshd.pid' )
        self.cmd( '/etc/init.d/ssh start' )

    def stopSSH( self ):
        "Stop sshd"
        self.cmd( '/etc/init.d/ssh stop' )

    def startOVS( self ):
        "Start OVS (will create new local ovsdb)"
        self.cmd( '/etc/init.d/openvswitch-switch start' )

    def stopOVS( self ):
        "Stop OVS"
        self.cmd( '/etc/init.d/openvswitch-switch stop' )

    def config( self, **kwargs ):
        "Start sshd and other stuff"
        self.ssh = kwargs.pop( 'ssh', False )
        self.ovs = kwargs.pop( 'ovs', False )
        super( MininetServer, self ).config( self, **kwargs )
        if self.ssh:
            self.startSSH()
        if self.ovs:
            self.startOVS()

    def terminate( self, *args, **kwargs ):
        if self.ssh:
            self.stopSSH()
        if self.ovs:
            self.stopOVS()
        super( MininetServer, self ).terminate( *args, **kwargs )


class ClusterTopo( Topo ):
    "Cluster topology: m1..mN"
    def build( self, n ):
        ms1 = self.addSwitch( 'ms1' )
        for i in range( 1, n + 1 ):
            h = self.addHost( 'm%d' % i )
            self.addLink( h, ms1 )


def test():
    "Test this setup"
    setLogLevel( 'info' )
    topo = ClusterTopo( 3 )
    host = partial( MininetServer, ssh=True, ovs=True )
    net = Mininet( topo=topo, host=host, ipBase='10.0/24' )
    # addNAT().configDefault() also connects root namespace to Mininet
    net.addNAT().configDefault()
    net.start()
    CLI( net )
    net.stop()

if __name__ == '__main__':
    test()
