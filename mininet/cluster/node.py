#!/usr/bin/python
# BL note: so little code is required for remote nodes,
# we will probably just want to update the main Node()
# class to enable it for remote access! However, there
# are a large number of potential failure conditions with
# remote nodes which we may want to detect and handle.
# Another interesting point is that we could put everything
# in a mix-in class and easily add cluster mode to 2.0.

from mininet.node import Node, Host, OVSSwitch, Controller
from mininet.log import setLogLevel, debug, info, error
from mininet.util import quietRun, errRun
from subprocess import Popen, PIPE, STDOUT
from mininet.cluster.clean import *
from mininet.cluster.link import RemoteLink

import os
from random import randrange
import sys
import re
from itertools import groupby
from operator import attrgetter
from distutils.version import StrictVersion


class RemoteMixin( object ):

    "A mix-in class to turn local nodes into remote nodes"

    # ssh base command
    # -q: don't print stupid diagnostic messages
    # BatchMode yes: don't ask for password
    # ForwardAgent yes: forward authentication credentials
    sshbase = [ 'ssh', '-q',
                '-o', 'BatchMode=yes',
                '-o', 'ForwardAgent=yes', '-tt' ]

    def __init__( self, name, server='localhost', user=None, serverIP=None,
                  controlPath=False, splitInit=False, **kwargs):
        """Instantiate a remote node
           name: name of remote node
           server: remote server (optional)
           user: user on remote server (optional)
           controlPath: specify shared ssh control path (optional)
           splitInit: split initialization?
           **kwargs: see Node()"""
        # We connect to servers by IP address
        self.server = server if server else 'localhost'
        self.serverIP = ( serverIP if serverIP
                          else self.findServerIP( self.server ) )
        self.user = user if user else findUser()
        ClusterCleanup.add( server=server, user=user )
        if controlPath is True:
            # Set a default control path for shared SSH connections
            controlPath = '/tmp/mn-%r@%h:%p'
        self.controlPath = controlPath
        self.splitInit = splitInit
        if self.user and self.server != 'localhost':
            self.dest = '%s@%s' % ( self.user, self.serverIP )
            self.sshcmd = [ 'sudo', '-E', '-u', self.user ] + self.sshbase
            if self.controlPath:
                self.sshcmd += [ '-o', 'ControlPath=' + self.controlPath,
                                 '-o', 'ControlMaster=auto',
                                 '-o', 'ControlPersist=' + '1' ]
            self.sshcmd += [ self.dest ]
            self.isRemote = True
        else:
            self.dest = None
            self.sshcmd = []
            self.isRemote = False
        # Satisfy pylint
        self.shell, self.pid = None, None
        super( RemoteMixin, self ).__init__( name, **kwargs )

    # Determine IP address of local host
    _ipMatchRegex = re.compile( r'\d+\.\d+\.\d+\.\d+' )

    @classmethod
    def findServerIP( cls, server ):
        "Return our server's IP address"
        # First, check for an IP address
        ipmatch = cls._ipMatchRegex.findall( server )
        if ipmatch:
            return ipmatch[ 0 ]
        # Otherwise, look up remote server
        output = quietRun( 'getent ahostsv4 %s' % server )
        ips = cls._ipMatchRegex.findall( output )
        ip = ips[ 0 ] if ips else None
        return ip

    # Command support via shell process in namespace
    def startShell( self, *args, **kwargs ):
        "Start a shell process for running commands"
        if self.isRemote:
            kwargs.update( mnopts='-c' )
        super( RemoteMixin, self ).startShell( *args, **kwargs )
        # Optional split initialization
        self.sendCmd( 'echo $$' )
        if not self.splitInit:
            self.finishInit()

    def finishInit( self ):
        "Wait for split initialization to complete"
        self.pid = int( self.waitOutput() )

    def rpopen( self, *cmd, **opts ):
        "Return a Popen object on underlying server in root namespace"
        params = { 'stdin': PIPE,
                   'stdout': PIPE,
                   'stderr': STDOUT,
                   'sudo': True }
        params.update( opts )
        return self._popen( *cmd, **params )

    def rcmd( self, *cmd, **opts):
        """rcmd: run a command on underlying server
           in root namespace
           args: string or list of strings
           returns: stdout and stderr"""
        popen = self.rpopen( *cmd, **opts )
        # print 'RCMD: POPEN:', popen
        # These loops are tricky to get right.
        # Once the process exits, we can read
        # EOF twice if necessary.
        result = ''
        while True:
            poll = popen.poll()
            result += popen.stdout.read()
            if poll is not None:
                break
        return result

    @staticmethod
    def _ignoreSignal():
        "Detach from process group to ignore all signals"
        os.setpgrp()

    def _popen( self, cmd, sudo=True, tt=True, **params):
        """Spawn a process on a remote node
            cmd: remote command to run (list)
            **params: parameters to Popen()
            returns: Popen() object"""
        if type( cmd ) is str:
            cmd = cmd.split()
        if self.isRemote:
            if sudo:
                cmd = [ 'sudo', '-E' ] + cmd
            if tt:
                cmd = self.sshcmd + cmd
            else:
                # Hack: remove -tt
                sshcmd = list( self.sshcmd )
                sshcmd.remove( '-tt' )
                cmd = sshcmd + cmd
        else:
            if self.user and not sudo:
                # Drop privileges
                cmd = [ 'sudo', '-E', '-u', self.user ] + cmd
        params.update( preexec_fn=self._ignoreSignal )
        debug( '_popen', cmd, '\n' )
        popen = super( RemoteMixin, self )._popen( cmd, **params )
        return popen

    def popen( self, *args, **kwargs ):
        "Override: disable -tt"
        return super( RemoteMixin, self).popen( *args, tt=False, **kwargs )

    def addIntf( self, *args, **kwargs ):
        "Override: use RemoteLink.moveIntf"
        kwargs.update( moveIntfFn=RemoteLink.moveIntf )
        return super( RemoteMixin, self).addIntf( *args, **kwargs )


class RemoteNode( RemoteMixin, Node ):
    "A node on a remote server"
    pass


class RemoteHost( RemoteNode ):
    "A RemoteHost is simply a RemoteNode"
    pass


class RemoteOVSSwitch( RemoteMixin, OVSSwitch ):
    "Remote instance of Open vSwitch"

    OVSVersions = {}

    def __init__( self, *args, **kwargs ):
        # No batch startup yet
        kwargs.update( batch=True )
        super( RemoteOVSSwitch, self ).__init__( *args, **kwargs )

    def isOldOVS( self ):
        "Is remote switch using an old OVS version?"
        cls = type( self )
        if self.server not in cls.OVSVersions:
            # pylint: disable=not-callable
            vers = self.cmd( 'ovs-vsctl --version' )
            # pylint: enable=not-callable
            cls.OVSVersions[ self.server ] = re.findall(
                r'\d+\.\d+', vers )[ 0 ]
        return ( StrictVersion( cls.OVSVersions[ self.server ] ) <
                 StrictVersion( '1.10' ) )

    @classmethod
    def batchStartup( cls, switches, **_kwargs ):
        "Start up switches in per-server batches"
        key = attrgetter( 'server' )
        for server, switchGroup in groupby( sorted( switches, key=key ), key ):
            info( '(%s)' % server )
            group = tuple( switchGroup )
            switch = group[ 0 ]
            OVSSwitch.batchStartup( group, run=switch.cmd )
        return switches

    @classmethod
    def batchShutdown( cls, switches, **_kwargs ):
        "Stop switches in per-server batches"
        key = attrgetter( 'server' )
        for server, switchGroup in groupby( sorted( switches, key=key ), key ):
            info( '(%s)' % server )
            group = tuple( switchGroup )
            switch = group[ 0 ]
            OVSSwitch.batchShutdown( group, run=switch.rcmd )
        return switches
