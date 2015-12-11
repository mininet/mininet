"""
Docker Node extends Mininet Node to enable running a Host or Switch
inside a Docker container.
"""

import os
import pty
import re
import select
import subprocess
import time

from mininet.node import Node, Switch, Host
from mininet.util import isShellBuiltin

class DockerNode( Node ):
    """A virtual node running in a docker container"""

    def __init__( self, name, image=None, port_map=None, fs_map=None,
                  **kwargs ):
        if image is None:
            raise UnboundLocalError( 'Docker image is not specified' )
        img_id = subprocess.check_output( [ 'docker', 'images', '-q', image ] )
        if not img_id:
            raise ValueError( 'Docker image "%s" does not exist' % image )
        self.docker_image = image
        self.port_map = port_map
        self.fs_map = fs_map
        kwargs[ 'inNamespace' ] = True
        Node.__init__( self, name, **kwargs )

    @classmethod
    def setup( cls ):
        pass

    def sendCmd( self, *args, **kwargs ):
        assert self.shell and not self.waiting
        printPid = kwargs.get( 'printPid', True )
        # Allow sendCmd( [ list ] )
        if len( args ) == 1 and isinstance( args[ 0 ], list ):
            cmd = args[ 0 ]
        # Allow sendCmd( cmd, arg1, arg2... )
        elif len( args ) > 0:
            cmd = args
        # Convert to string
        if not isinstance( cmd, str ):
            cmd = ' '.join( [ str( c ) for c in cmd ] )
        if not re.search( r'\w', cmd ):
            # Replace empty commands with something harmless
            cmd = 'echo -n'
        self.lastCmd = cmd
        printPid = printPid and not isShellBuiltin( cmd )
        if len( cmd ) > 0 and cmd[ -1 ] == '&':
            # print ^A{pid}\n{sentinel}
            cmd += ' printf "\\001%d\\012" $! '
        else:
            pass
        self.write( cmd + '\n' )
        self.lastPid = None
        self.waiting = True

    def popen( self, *args, **kwargs ):
        mncmd = [ 'docker', 'exec', self.name ]
        return Node.popen( self, *args, mncmd=mncmd, **kwargs )

    def stop( self, deleteIntfs=False ):
        dev_null = open(os.devnull, 'w')
        subprocess.call( [ 'docker rm -f ' + self.name ],
                         stdin=dev_null, stdout=dev_null,
                         stderr=dev_null, shell=True )
        dev_null.close()
        Node.stop( self, deleteIntfs )

    def startShell( self, mnopts=None ):
        self.stop()

        args = ['docker', 'run', '-ti', '--rm', '--privileged=true']
        args.extend( [ '--hostname=' + self.name, '--name=' + self.name ] )
        args.extend( [ '-e', 'DISPLAY'] )
        args.extend( [ '-v', '/tmp/.X11-unix:/tmp/.X11-unix:ro' ] )
        if self.port_map is not None:
            for p in self.port_map:
                args.extend( [ '-p', '%d:%d' % ( p[ 0 ], p[ 1 ] ) ] )
        if self.fs_map is not None:
            for f in self.fs_map:
                args.extend( [ '-v', '%s:%s' % ( f[ 0 ], f[ 1 ] ) ] )
        args.extend( [ self.docker_image ] )

        master, slave = pty.openpty()
        self.shell = subprocess.Popen( args,
                                       stdin=slave, stdout=slave, stderr=slave,
                                       close_fds=True,
                                       preexec_fn=os.setpgrp )
        os.close( slave )
        ttyobj = os.fdopen( master, 'rw' )
        self.stdin = ttyobj
        self.stdout = ttyobj
        self.pid = self.shell.pid
        self.pollOut = select.poll()
        self.pollOut.register( self.stdout )
        self.outToNode[ self.stdout.fileno() ] = self
        self.inToNode[ self.stdin.fileno() ] = self
        self.execed = False
        self.lastCmd = None
        self.lastPid = None
        self.readbuf = ''
        self.waiting = False

        # Wait for prompt
        time.sleep(1)

        pid_cmd = ['docker', 'inspect', '--format=\'{{ .State.Pid }}\'',
                   self.name ]
        pidp = subprocess.Popen( pid_cmd, stdin=subprocess.PIPE,
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT, close_fds=False )
        pidp.wait()
        ps_out = pidp.stdout.readlines()
        self.pid = int(ps_out[0])
        self.cmd( 'export PS1=\"\\177\"; printf "\\177"' )
        self.cmd( 'stty -echo; set +m' )

class DockerSwitch( DockerNode, Switch ):
    """A Docker switch is a Docker Node with switch functionality"""
    def start( self, controllers ):
        """Start the switch"""
        pass

class DockerHost( DockerNode, Host ):
    """A Docker host is the same as a Docker Node"""
    pass
