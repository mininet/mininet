"""
Mininet Cleanup
author: Bob Lantz (rlantz@cs.stanford.edu)

Unfortunately, Mininet and OpenFlow (and the Linux kernel)
don't always clean up properly after themselves. Until they do
(or until cleanup functionality is integrated into the Python
code), this script may be used to get rid of unwanted garbage.
It may also get rid of 'false positives', but hopefully
nothing irreplaceable!
"""

from subprocess import Popen, PIPE

from mininet.log import info
from mininet.term import cleanUpScreens

def sh( cmd ):
    "Print a command and send it to the shell"
    info( cmd + '\n' )
    return Popen( [ '/bin/sh', '-c', cmd ], stdout=PIPE ).communicate()[ 0 ]

def cleanup():
    """Clean up junk which might be left over from old runs;
       do fast stuff before slow dp and link removal!"""

    info("*** Removing excess controllers/ofprotocols/ofdatapaths/pings/noxes"
         "\n")
    zombies = 'controller ofprotocol ofdatapath ping nox_core lt-nox_core '
    zombies += 'ovs-openflowd udpbwtest'
    # Note: real zombie processes can't actually be killed, since they
    # are already (un)dead. Then again,
    # you can't connect to them either, so they're mostly harmless.
    sh( 'killall -9 ' + zombies + ' 2> /dev/null' )

    info( "*** Removing junk from /tmp\n" )
    sh( 'rm -f /tmp/vconn* /tmp/vlogs* /tmp/*.out /tmp/*.log' )

    info( "*** Removing old screen sessions\n" )
    cleanUpScreens()

    info( "*** Removing excess kernel datapaths\n" )
    dps = sh( "ps ax | egrep -o 'dp[0-9]+' | sed 's/dp/nl:/'" ).split( '\n' )
    for dp in dps:
        if dp != '':
            sh( 'dpctl deldp ' + dp )

    info( "*** Removing all links of the pattern foo-ethX\n" )
    links = sh( "ip link show | egrep -o '(\w+-eth\w+)'" ).split( '\n' )
    for link in links:
        if link != '':
            sh( "ip link del " + link )

    info( "*** Cleanup complete.\n" )
