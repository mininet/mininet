#!/usr/bin/env python
'''Utility functions for Mininet.'''

from time import sleep
import select
from subprocess import call, check_call, Popen, PIPE, STDOUT

from mininet.logging_mod import lg


def run(cmd):
    '''Simple interface to subprocess.call()

     @param cmd list of command params
    '''
    return call(cmd.split(' '))


def checkRun(cmd):
    '''Simple interface to subprocess.check_call()

    @param cmd list of command params
    '''
    check_call(cmd.split(' '))


def quietRun(cmd):
    '''Run a command, routing stderr to stdout, and return the output.

    @param cmd list of command params
    '''
    if isinstance(cmd, str):
        cmd = cmd.split(' ')
    popen = Popen(cmd, stdout=PIPE, stderr=STDOUT)
    # We can't use Popen.communicate() because it uses
    # select(), which can't handle
    # high file descriptor numbers! poll() can, however.
    output = ''
    readable = select.poll()
    readable.register(popen.stdout)
    while True:
        while readable.poll():
            data = popen.stdout.read(1024)
            if len(data) == 0:
                break
            output += data
        popen.poll()
        if popen.returncode != None:
            break
    return output


def make_veth_pair(intf1, intf2):
    '''Create a veth pair connecting intf1 and intf2.

    @param intf1 string, interface name
    @param intf2 string, interface name
    '''
    # Delete any old interfaces with the same names
    quietRun('ip link del ' + intf1)
    quietRun('ip link del ' + intf2)
    # Create new pair
    cmd = 'ip link add name ' + intf1 + ' type veth peer name ' + intf2
    #lg.info('running command: %s\n' % cmd)
    return checkRun(cmd)


def move_intf(intf, node):
    '''Move interface to node.

    @param intf string interface name
    @param node Node object

    @return success boolean, did operation complete?
    '''
    cmd = 'ip link set ' + intf + ' netns ' + repr(node.pid)
    #lg.info('running command: %s\n' % cmd)
    quietRun(cmd)
    #lg.info(' output: %s\n' % output)
    links = node.cmd('ip link show')
    if not intf in links:
        lg.error('*** Error: move_intf: % not successfully moved to %s:\n' %
                 (intf, node.name))
        return False
    return True


# Interface management
#
# Interfaces are managed as strings which are simply the
# interface names, of the form 'nodeN-ethM'.
#
# To connect nodes, we create a pair of veth interfaces, and then place them
# in the pair of nodes that we want to communicate. We then update the node's
# list of interfaces and connectivity map.
#
# For the kernel datapath, switch interfaces
# live in the root namespace and thus do not have to be
# explicitly moved.

def makeIntfPair(intf1, intf2):
    '''Make a veth pair.

    @param intf1 string, interface
    @param intf2 string, interface
    @return success boolean
    '''
    # Delete any old interfaces with the same names
    quietRun('ip link del ' + intf1)
    quietRun('ip link del ' + intf2)
    # Create new pair
    cmd = 'ip link add name ' + intf1 + ' type veth peer name ' + intf2
    return checkRun( cmd )


def moveIntf(intf, node, print_error = False):
    '''Move interface to node.

    @param intf string, interface
    @param node Node object
    @param print_error if true, print error
    '''
    cmd = 'ip link set ' + intf + ' netns ' + repr(node.pid)
    quietRun(cmd)
    links = node.cmd('ip link show')
    if not intf in links:
        if print_error:
            lg.error('*** Error: moveIntf: % not successfully moved to %s:\n' %
                     (intf, node.name))
        return False
    return True


def retry(n, retry_delay, fn, *args):
    '''Try something N times before giving up.

    @param n number of times to retry
    @param retry_delay seconds wait this long between tries
    @param fn function to call
    @param args args to apply to function call
    '''
    tries = 0
    while not apply(fn, args) and tries < n:
        sleep(retry_delay)
        tries += 1
    if tries >= n:
        lg.error("*** gave up after %i retries\n" % tries)
        exit( 1 )


# delay between interface move checks in seconds
MOVEINTF_DELAY = 0.0001

def createLink(node1, node2):
    '''Create a link between nodes, making an interface for each.

    @param node1 Node object
    @param node2 Node object
    '''
    intf1 = node1.newIntf()
    intf2 = node2.newIntf()
    makeIntfPair(intf1, intf2)
    if node1.inNamespace:
        retry(3, MOVEINTF_DELAY, moveIntf, intf1, node1)
    if node2.inNamespace:
        retry(3, MOVEINTF_DELAY, moveIntf, intf2, node2)
    node1.connection[intf1] = (node2, intf2)
    node2.connection[intf2] = (node1, intf1)
    return intf1, intf2