#!/usr/bin/python

"""
Convert simple documentation to epydoc/pydoctor-compatible markup
"""

from sys import stdin, stdout, argv
import os
from tempfile import mkstemp
from subprocess import call

import re

spaces = re.compile( r'\s+' )
singleLineExp = re.compile( r'\s+"([^"]+)"' )
commentStartExp = re.compile( r'\s+"""' )
commentEndExp = re.compile( r'"""$' )
returnExp = re.compile( r'\s+(returns:.*)' )
lastindent = ''


comment = False

def fixParam( line ):
    "Change foo: bar to @foo bar"
    result = re.sub( r'(\w+):', r'@param \1', line )
    result = re.sub( r'   @', r'@', result)
    return result

def fixReturns( line ):
    "Change returns: foo to @return foo"
    return re.sub( 'returns:', r'@returns', line )
    
def fixLine( line ):
    global comment
    match = spaces.match( line )
    if not match:
        return line
    else:
        indent = match.group(0)
    if singleLineExp.match( line ):
        return re.sub( '"', '"""', line )
    if commentStartExp.match( line ):
        comment = True
    if comment:
        line = fixReturns( line )
        line = fixParam( line )
    if commentEndExp.search( line ):
        comment = False
    return line


def test():
    "Test transformations"
    assert fixLine(' "foo"') == ' """foo"""'
    assert fixParam( 'foo: bar' ) == '@param foo bar'
    assert commentStartExp.match( '   """foo"""')

def funTest():
    testFun = (
    'def foo():\n'
    '   "Single line comment"\n'
    '   """This is a test"""\n'
    '      bar: int\n'
    '      baz: string\n'
    '      returns: junk"""\n'
    '   if True:\n'
    '       print "OK"\n'
    ).splitlines( True )

    fixLines( testFun )
    
def fixLines( lines, fid ):
    for line in lines:
        os.write( fid, fixLine( line ) )

if __name__ == '__main__':
    if False:
        funTest()
    infile = open( argv[1] )
    outfid, outname = mkstemp()
    fixLines( infile.readlines(), outfid )
    infile.close()
    os.close( outfid )
    call( [ 'doxypy.py', outname ] )



    
