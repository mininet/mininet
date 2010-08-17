"Module dependency utility functions for Mininet."

from mininet.util import quietRun
from mininet.log import info, error, debug
from os import environ

def lsmod():
    "Return output of lsmod."
    return quietRun( 'lsmod' )

def rmmod( mod ):
    """Return output of lsmod.
       mod: module string"""
    return quietRun( [ 'rmmod', mod ] )

def modprobe( mod ):
    """Return output of modprobe
       mod: module string"""
    return quietRun( [ 'modprobe', mod ] )

OF_KMOD = 'ofdatapath'
OVS_KMOD = 'openvswitch_mod'
TUN = 'tun'

def moduleDeps( subtract=None, add=None ):
    """Handle module dependencies.
       subtract: string or list of module names to remove, if already loaded
       add: string or list of module names to add, if not already loaded"""
    subtract = subtract if subtract is not None else []
    add = add if add is not None else []
    if type( subtract ) is str:
        subtract = [ subtract ]
    if type( add ) is str:
        add = [ add ]
    for mod in subtract:
        if mod in lsmod():
            info( '*** Removing ' + mod + '\n' )
            rmmodOutput = rmmod( mod )
            if rmmodOutput:
                error( 'Error removing ' + mod + '\n%s' % rmmodOutput )
                exit( 1 )
            if mod in lsmod():
                error( 'Failed to remove ' + mod + '; still there!\n' )
                exit( 1 )
    for mod in add:
        if mod not in lsmod():
            info( '*** Loading ' + mod + '\n' )
            modprobeOutput = modprobe( mod )
            if modprobeOutput:
                error( 'Error inserting ' + mod + ';\n See INSTALL.\n%s' %
                       modprobeOutput )
                exit( 1 )
            if mod not in lsmod():
                error( 'Failed to insert ' + mod + '\n' )
                exit( 1 )
        else:
            debug( '*** ' + mod + ' already loaded\n' )

def pathCheck( *args ):
    "Make sure each program in *args can be found in $PATH."
    for arg in args:
        if not quietRun( 'which ' + arg ):
            error( 'Cannot find required executable %s -'
                ' is it installed somewhere in your $PATH?\n(%s)\n' %
                    ( arg, environ[ 'PATH' ] ) )
            exit( 1 )
