#!/usr/bin/python

"""
bind.py: Bind mount prototype

This creates hosts with private directories as desired.
"""

from mininet.net import Mininet
from mininet.node import Host, Switch, Controller
from mininet.cli import CLI
from mininet.util import errFail, quietRun, errRun
from mininet.topo import SingleSwitchTopo
from mininet.log import setLogLevel, info, debug

from os.path import join, realpath
from functools import partial

# Utility functions for unmounting a tree

def mountPoints():
    "Return list of mounted file systems"
    mtab, _err, _ret = errFail( 'cat /proc/mounts' )
    lines = mtab.split( '\n' )
    mounts = []
    for line in lines:
        if not line:
            continue
        fields = line.split( ' ')
        mount = fields[ 1 ]
        mounts.append( mount )
    return mounts

def unmountAll( dir='/var/run/mn' ):
    "Unmount all mounts under a directory tree"
    dir = realpath( dir )
    # Find all mounts below dir
    # This is subtle because /foo is not
    # a parent of /foot
    dirslash = dir + '/'
    mounts = [ m for m in mountPoints()
              if m == dir or m.find( dirslash ) == 0 ]
    # Unmount them from bottom to top
    mounts.sort( reverse=True )
    for mount in mounts:
        debug( 'Unmounting', mount, '\n' )
        out, err, code = errRun( 'umount', mount )
        if code != 0:
            info( '*** Warning: failed to umount', mount, '\n' )
            info( err )


class HostWithPrivateDirs( Host ):
    "Host with private directories"

    mnRunDir = realpath( '/var/run/mn' )

    def __init__(self, name, *args, **kwargs ):
        "privateDirs: list of private directories"
        self.privateDirs = kwargs.pop( 'privateDirs', [] )
        Host.__init__( self, name, *args, **kwargs )
        self.rundir = '%s/%s' % ( self.mnRunDir, name )
        if self.privateDirs:
            self.privateDirs = [ realpath( d ) for d in self.privateDirs ]
            self.createBindMounts()
        # These should run in the namespace before we chroot,
        # in order to put the right entries in /etc/mtab
        # Eventually this will allow a local pid space
        # Now we chroot and cd to wherever we were before.
        pwd = self.cmd( 'pwd' ).strip()
        self.sendCmd( 'exec chroot', self.root, 'bash -ms mininet:'
                       + self.name )
        self.waiting = False
        self.cmd( 'cd', pwd )
        # In order for many utilities to work,
        # we need to remount /proc and /sys
        self.cmd( 'mount /proc' )
        self.cmd( 'mount /sys' )

    def mountPrivateDirs( self ):
        "Create and bind mount private dirs"
        for dir in self.privateDirs:
            privateDir = self.private + dir
            errFail( 'mkdir -p ' + privateDir )
            mountPoint = self.root + dir
            errFail( 'mount -B %s %s' %
                           ( privateDir, mountPoint) )

    def remountDirs( self, fstypes=[ 'nfs' ] ):
        "Remount mounted file systems"
        dirs = self.cmd( 'cat /proc/mounts' ).strip().split( '\n' )
        for dir in dirs:
            line = dir.split()
            mountpoint, fstype = line[ 1 ], line[ 2 ]
            # Don't re-remount directories!!!
            if mountpoint.find( self.mnRunDir ) == 0:
                continue
            if fstype in fstypes:
                print "remounting:", mountpoint
                errFail( 'mount -B %s %s' % (
                         mountpoint, self.root + mountpoint ) )

    def createBindMounts( self ):
        """Create a chroot directory structure,
           with self.privateDirs as private dirs"""
        errFail( 'mkdir -p '+ self.rundir )
        unmountAll( self.rundir )
        # Create /root and /private directories
        self.root = self.rundir + '/root'
        self.private = self.rundir + '/private'
        errFail( 'mkdir -p ' + self.root )
        errFail( 'mkdir -p ' + self.private )
        # Recursively mount / in private doort
        # note we'll remount /sys and /proc later
        errFail( 'mount -B / ' + self.root )
        self.remountDirs()
        self.mountPrivateDirs()

    def unmountBindMounts( self ):
        "Unmount all of our bind mounts"
        unmountAll( self.rundir )

    def popen( self, *args, **kwargs ):
        "Popen with chroot support"
        chroot = kwargs.pop( 'chroot', True )
        mncmd = kwargs.get( 'mncmd',
                           [ 'mnexec', '-a', str( self.pid ) ] )
        if chroot:
            mncmd = [ 'chroot', self.root ] + mncmd
            kwargs[ 'mncmd' ] = mncmd
        return Host.popen( self, *args, **kwargs )

    def cleanup( self ):
        "Clean up, then unmount bind mounts"
        # Wait for process to actually terminate
        self.shell.wait()
        Host.cleanup( self )
        self.unmountBindMounts()
        errFail( 'rmdir ' + self.root )

# Sample usage

def testHostWithPrivateDirs():
    "Test bind mounts"
    topo = SingleSwitchTopo( 2 )
    privateDirs = [ '/var/log', '/var/run' ]
    host = partial( HostWithPrivateDirs, privateDirs=privateDirs )
    net = Mininet( topo=topo, host=host )
    net.start()
    print 'Private Directories:', privateDirs
    CLI( net )
    net.stop()


if __name__ == '__main__':
    unmountAll()
    setLogLevel( 'info' )
    testHostWithPrivateDirs()
    unmountAll()





