#!/usr/bin/env python

from subprocess import check_output as co
from sys import exit, version_info

def run(*args, **kwargs):
    "Run co and decode for python3"
    result = co(*args, **kwargs)
    return result.decode() if version_info[ 0 ] >= 3 else result

# Actually run bin/mn rather than importing via python path
version = 'Mininet ' + run( 'PYTHONPATH=. bin/mn --version 2>&1', shell=True )
version = version.strip()

# Find all Mininet path references
lines = run( "egrep -or 'Mininet [0-9\.\+]+\w*' *", shell=True )

error = False

for line in lines.split( '\n' ):
    if line and 'Binary' not in line:
        fname, fversion = line.split( ':' )
        if version != fversion:
            print( "%s: incorrect version '%s' (should be '%s')" % (
                fname, fversion, version ) )
            error = True

if error:
    exit( 1 )
