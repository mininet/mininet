#!/usr/bin/python

"""
bind.py: Bind mount prototype

This creates hosts with private directories as desired.
"""

from mininet.net import Mininet
from mininet.node import Host
from mininet.cli import CLI
from mininet.util import errFail, quietRun, errRun
from mininet.topo import SingleSwitchTopo
from mininet.log import setLogLevel, info, debug

from os.path import realpath
from functools import partial


# Utility functions for unmounting a tree

MNRUNDIR = realpath( '/var/run/mn' )

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

def unmountAll( rootdir=MNRUNDIR ):
    "Unmount all mounts under a directory tree"
    rootdir = realpath( rootdir )
    # Find all mounts below rootdir
    # This is subtle because /foo is not
    # a parent of /foot
    dirslash = rootdir + '/'
    mounts = [ m for m in mountPoints()
              if m == dir or m.find( dirslash ) == 0 ]
    # Unmount them from bottom to top
    mounts.sort( reverse=True )
    for mount in mounts:
        debug( 'Unmounting', mount, '\n' )
        _out, err, code = errRun( 'umount', mount )
        if code != 0:
            info( '*** Warning: failed to umount', mount, '\n' )
            info( err )


class HostWithPrivateDirs( Host ):
    "Host with private directories"

    mnRunDir = MNRUNDIR

    def __init__(self, name, *args, **kwargs ):
        """privateDirs: list of private directories
           remounts: dirs to remount
           unmount: unmount dirs in cleanup? (True)
           Note: if unmount is False, you must call unmountAll()
           manually."""
        self.privateDirs = kwargs.pop( 'privateDirs', [] )
        self.remounts = kwargs.pop( 'remounts', [] )
        self.unmount = kwargs.pop( 'unmount', True )
        Host.__init__( self, name, *args, **kwargs )
        self.rundir = '%s/%s' % ( self.mnRunDir, name )
        self.root, self.private = None, None  # set in createBindMounts
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
        for dir_ in self.privateDirs:
            privateDir = self.private + dir_
            errFail( 'mkdir -p ' + privateDir )
            mountPoint = self.root + dir_
            errFail( 'mount -B %s %s' %
                           ( privateDir, mountPoint) )

    def mountDirs( self, dirs ):
        "Mount a list of directories"
        for dir_ in dirs:
            mountpoint = self.root + dir_
            errFail( 'mount -B %s %s' %
                     ( dir_, mountpoint ) )

    @classmethod
    def findRemounts( cls, fstypes=None ):
        """Identify mount points in /proc/mounts to remount
           fstypes: file system types to match"""
        if fstypes is None:
            fstypes = [ 'nfs' ]
        dirs = quietRun( 'cat /proc/mounts' ).strip().split( '\n' )
        remounts = []
        for dir_ in dirs:
            line = dir_.split()
            mountpoint, fstype = line[ 1 ], line[ 2 ]
            # Don't re-remount directories!!!
            if mountpoint.find( cls.mnRunDir ) == 0:
                continue
            if fstype in fstypes:
                remounts.append( mountpoint )
        return remounts

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
        self.mountDirs( self.remounts )
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
        """Clean up, then unmount bind mounts
           unmount: actually unmount bind mounts?"""
        # Wait for process to actually terminate
        self.shell.wait()
        Host.cleanup( self )
        if self.unmount:
            self.unmountBindMounts()
            errFail( 'rmdir ' + self.root )


# Convenience aliases

findRemounts = HostWithPrivateDirs.findRemounts


# Sample usage

def testHostWithPrivateDirs():
    "Test bind mounts"
    topo = SingleSwitchTopo( 10 )
    remounts = findRemounts( fstypes=[ 'nfs' ] )
    privateDirs = [ '/var/log', '/var/run' ]
    host = partial( HostWithPrivateDirs, remounts=remounts,
                    privateDirs=privateDirs, unmount=False )
    net = Mininet( topo=topo, host=host )
    net.start()
    info( 'Private Directories:', privateDirs, '\n' )
    CLI( net )
    net.stop()
    # We do this all at once to save a bit of time
    info( 'Unmounting host bind mounts...\n' )
    unmountAll()


if __name__ == '__main__':
    unmountAll()
    setLogLevel( 'info' )
    testHostWithPrivateDirs()
    info( 'Done.\n')




