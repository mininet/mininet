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

from subprocess import Popen, PIPE, STDOUT, check_output as co
from sys import stdout, exit
from time import sleep

from mininet.log import info
from mininet.term import cleanUpScreens

def sh( cmd ):
    "Run a command in the shell and return non-empty output lines"
    info( cmd + '\n' )
    output = ( Popen( [ '/bin/sh', '-c', cmd ], stdout=PIPE )
            .communicate()[ 0 ]
            .strip()
            .split( '\n' ) )
    return [ s for s in output if s ]

def cleanup():
    """Clean up junk which might be left over from old runs;
       do fast stuff before slow dp and link removal!"""

    info( "*** Removing excess "
          "controllers/ofprotocols/ofdatapaths/pings/noxes\n" )
    zombies = 'controller ofprotocol ofdatapath ping nox_core lt-nox_core '
    zombies += 'ovs-openflowd ovs-controller udpbwtest mnexec'
    # Note: real zombie processes can't actually be killed, since they
    # are already (un)dead. Then again,
    # you can't connect to them either, so they're mostly harmless.
    sh( 'killall -9 ' + zombies + ' 2> /dev/null' )

    # And kill off sudo mnexec
    sh( 'pkill -9 -f "sudo mnexec"')

    info( "*** Removing junk from /tmp\n" )
    sh( 'rm -f /tmp/vconn* /tmp/vlogs* /tmp/*.out /tmp/*.log' )

    info( "*** Removing old X11 tunnels\n" )
    cleanUpScreens()

    info( "*** Removing excess kernel datapaths\n" )
    dps = sh( "ps ax | egrep -o 'dp[0-9]+' | sed 's/dp/nl:/'" )
    for dp in dps:
        sh( 'dpctl deldp ' + dp )

    info( "*** Removing OVS datapaths\n" )
    dps = sh("ovs-vsctl list-br")
    for dp in dps:
        sh( 'ovs-vsctl del-br ' + dp )
    if co( 'ovs-vsctl list-br', shell=True ):
        raise Excpetion( "Error: could not remove all OVS datapaths" )

    info( "*** Removing all links of the pattern foo-ethX\n" )
    links = sh( "ip link show | egrep -o '(\w+-eth\w+)'" )
    for link in links:
        sh( "ip link del " + link )
    if sh( "ip link show | egrep -o '(\w+-eth\w+)'" ):
        raise Exception( "Error could not remove stale links")

    info( "*** Killing stale mininet processes\n" )
    sh( 'pkill -9 -f mininet' )
    # Make sure they are gone
    while True:
        try:
            pids = co( 'pgrep -f mininet'.split() )
        except:
            pids = ''
        if pids:
            sh( 'pkill -f 9 mininet' )
            sleep( .5 )
        else:
            break

    info( "*** Removing stale namespaces\n" )
    nses = sh( "ip netns list" )
    for ns in nses:
        sh( "ip netns del " + ns )
    if co( "ip netns list", shell=True ):
        raise Exception( "Error: could not remove stale namespaces" )

    info( "*** Cleanup complete.\n" )
