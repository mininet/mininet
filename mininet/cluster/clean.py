#!/usr/bin/python

from mininet.clean import addCleanupCallback
from mininet.log import setLogLevel, debug, info, error
from mininet.util import quietRun, errRun

import os


def findUser():
    "Try to return logged-in (usually non-root) user"
    return (
            # If we're running sudo
            os.environ.get( 'SUDO_USER', False ) or
            # Logged-in user (if we have a tty)
            ( quietRun( 'who am i' ).split() or [ False ] )[ 0 ] or
            # Give up and return effective user
            quietRun( 'whoami' ).strip() )


class ClusterCleanup( object ):
    "Cleanup callback"

    inited = False
    serveruser = {}

    @classmethod
    def add( cls, server, user='' ):
        "Add an entry to server: user dict"
        if not cls.inited:
            addCleanupCallback( cls.cleanup )
        if not user:
            user = findUser()
        cls.serveruser[ server ] = user

    @classmethod
    def cleanup( cls ):
        "Clean up"
        info( '*** Cleaning up cluster\n' )
        for server, user in cls.serveruser.iteritems():
            if server == 'localhost':
                # Handled by mininet.clean.cleanup()
                continue
            else:
                cmd = [ 'su', user, '-c',
                        'ssh %s@%s sudo mn -c' % ( user, server ) ]
                info( cmd, '\n' )
                info( quietRun( cmd ) )
