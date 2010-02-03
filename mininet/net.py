#!/usr/bin/python
"""Mininet: A simple networking testbed for OpenFlow!

@author Bob Lantz (rlantz@cs.stanford.edu)
@author Brandon Heller (brandonh@stanford.edu)

Mininet creates scalable OpenFlow test networks by using
process-based virtualization and network namespaces.

Simulated hosts are created as processes in separate network
namespaces. This allows a complete OpenFlow network to be simulated on
top of a single Linux kernel.

Each host has:
   A virtual console (pipes to a shell)
   A virtual interfaces (half of a veth pair)
   A parent shell (and possibly some child processes) in a namespace

Hosts have a network interface which is configured via ifconfig/ip
link/etc.

This version supports both the kernel and user space datapaths
from the OpenFlow reference implementation.

In kernel datapath mode, the controller and switches are simply
processes in the root namespace.

Kernel OpenFlow datapaths are instantiated using dpctl(8), and are
attached to the one side of a veth pair; the other side resides in the
host namespace. In this mode, switch processes can simply connect to the
controller via the loopback interface.

In user datapath mode, the controller and switches are full-service
nodes that live in their own network namespaces and have management
interfaces and IP addresses on a control network (e.g. 10.0.123.1,
currently routed although it could be bridged.)

In addition to a management interface, user mode switches also have
several switch interfaces, halves of veth pairs whose other halves
reside in the host nodes that the switches are connected to.

Naming:
   Host nodes are named h1-hN
   Switch nodes are named s0-sN
   Interfaces are named {nodename}-eth0 .. {nodename}-ethN,

"""
import os
import re
import signal
from subprocess import call
import sys
from time import sleep

from mininet.log import lg
from mininet.node import KernelSwitch, OVSKernelSwitch
from mininet.util import quietRun, fixLimits
from mininet.util import make_veth_pair, move_intf, retry, MOVEINTF_DELAY
from mininet.xterm import cleanUpScreens, makeXterms

DATAPATHS = ['kernel'] #['user', 'kernel']


def init():
    "Initialize Mininet."
    if os.getuid() != 0:
        # Note: this script must be run as root
        # Perhaps we should do so automatically!
        print "*** Mininet must run as root."
        exit(1)
    # If which produces no output, then netns is not in the path.
    # May want to loosen this to handle netns in the current dir.
    if not quietRun(['which', 'netns']):
        raise Exception("Could not find netns; see INSTALL")
    fixLimits()


class Mininet(object):
    '''Network emulation with hosts spawned in network namespaces.'''

    def __init__(self, topo, switch, host, controller, cparams,
                 build = True, xterms = False, cleanup = False,
                 in_namespace = False,
                 auto_set_macs = False, auto_static_arp = False):
        '''Create Mininet object.

        @param topo Topo object
        @param switch Switch class
        @param host Host class
        @param controller Controller class
        @param cparams ControllerParams object
        @param now build now?
        @param xterms if build now, spawn xterms?
        @param cleanup if build now, cleanup before creating?
        @param in_namespace spawn switches and controller in net namespaces?
        @param auto_set_macs set MAC addrs to DPIDs?
        @param auto_static_arp set all-pairs static MAC addrs?
        '''
        self.topo = topo
        self.switch = switch
        self.host = host
        self.controller = controller
        self.cparams = cparams
        self.nodes = {} # dpid to Node{Host, Switch} objects
        self.controllers = {} # controller name to Controller objects
        self.dps = 0 # number of created kernel datapaths
        self.in_namespace = in_namespace
        self.xterms = xterms
        self.cleanup = cleanup
        self.auto_set_macs = auto_set_macs
        self.auto_static_arp = auto_static_arp

        self.terms = [] # list of spawned xterm processes

        if build:
            self.build()

    def _add_host(self, dpid):
        '''Add host.

        @param dpid DPID of host to add
        '''
        host = self.host('h_' + self.topo.name(dpid))
        # for now, assume one interface per host.
        host.intfs.append('h_' + self.topo.name(dpid) + '-eth0')
        self.nodes[dpid] = host
        #lg.info('%s ' % host.name)

    def _add_switch(self, dpid):
        '''Add switch.

        @param dpid DPID of switch to add
        '''
        sw = None
        sw_dpid = None
        if self.auto_set_macs:
            sw_dpid = dpid
        if self.switch is KernelSwitch or self.switch is OVSKernelSwitch:
            sw = self.switch('s_' + self.topo.name(dpid), dp = self.dps,
                             dpid = sw_dpid)
            self.dps += 1
        else:
            sw = self.switch('s_' + self.topo.name(dpid))
        self.nodes[dpid] = sw

    def _add_link(self, src, dst):
        '''Add link.

        @param src source DPID
        @param dst destination DPID
        '''
        src_port, dst_port = self.topo.port(src, dst)
        src_node = self.nodes[src]
        dst_node = self.nodes[dst]
        src_intf = src_node.intfName(src_port)
        dst_intf = dst_node.intfName(dst_port)
        make_veth_pair(src_intf, dst_intf)
        src_node.intfs.append(src_intf)
        dst_node.intfs.append(dst_intf)
        src_node.ports[src_port] = src_intf
        dst_node.ports[dst_port] = dst_intf
        #lg.info('\n')
        #lg.info('added intf %s to src node %x\n' % (src_intf, src))
        #lg.info('added intf %s to dst node %x\n' % (dst_intf, dst))
        if src_node.inNamespace:
            #lg.info('moving src w/inNamespace set\n')
            retry(3, MOVEINTF_DELAY, move_intf, src_intf, src_node)
        if dst_node.inNamespace:
            #lg.info('moving dst w/inNamespace set\n')
            retry(3, MOVEINTF_DELAY, move_intf, dst_intf, dst_node)
        src_node.connection[src_intf] = (dst_node, dst_intf)
        dst_node.connection[dst_intf] = (src_node, src_intf)

    def _add_controller(self, controller):
        '''Add controller.

        @param controller Controller class
        '''
        controller = self.controller('c0', self.in_namespace)
        if controller: # allow controller-less setups
            self.controllers['c0'] = controller

    # Control network support:
    #
    # Create an explicit control network. Currently this is only
    # used by the user datapath configuration.
    #
    # Notes:
    #
    # 1. If the controller and switches are in the same (e.g. root)
    #    namespace, they can just use the loopback connection.
    #    We may wish to do this for the user datapath as well as the
    #    kernel datapath.
    #
    # 2. If we can get unix domain sockets to work, we can use them
    #    instead of an explicit control network.
    #
    # 3. Instead of routing, we could bridge or use 'in-band' control.
    #
    # 4. Even if we dispense with this in general, it could still be
    #    useful for people who wish to simulate a separate control
    #    network (since real networks may need one!)

    def _configureControlNetwork(self):
        '''Configure control network.'''
        self._configureRoutedControlNetwork()

    def _configureRoutedControlNetwork(self):
        '''Configure a routed control network on controller and switches.

        For use with the user datapath only right now.

        @todo(brandonh) Test this code!
        '''
        # params were: controller, switches, ips

        controller = self.controllers['c0']
        lg.info('%s <-> ' % controller.name)
        for switch_dpid in self.topo.switches():
            switch = self.nodes[switch_dpid]
            lg.info('%s ' % switch.name)
            sip = self.topo.ip(switch_dpid)#ips.next()
            sintf = switch.intfs[0]
            node, cintf = switch.connection[sintf]
            if node != controller:
                lg.error('*** Error: switch %s not connected to correct'
                         'controller' %
                         switch.name)
                exit(1)
            controller.setIP(cintf, self.cparams.ip, '/' +
                             self.cparams.subnet_size)
            switch.setIP(sintf, sip, '/' + self.cparams.subnet_size)
            controller.setHostRoute(sip, cintf)
            switch.setHostRoute(self.cparams.ip, sintf)
        lg.info('\n')
        lg.info('*** Testing control network\n')
        while not controller.intfIsUp(controller.intfs[0]):
            lg.info('*** Waiting for %s to come up\n', controller.intfs[0])
            sleep(1)
        for switch_dpid in self.topo.switches():
            switch = self.nodes[switch_dpid]
            while not switch.intfIsUp(switch.intfs[0]):
                lg.info('*** Waiting for %s to come up\n' % switch.intfs[0])
                sleep(1)
            if self.ping(hosts = [switch, controller]) != 0:
                lg.error('*** Error: control network test failed\n')
                exit(1)
        lg.info('\n')

    def _config_hosts(self):
        '''Configure a set of hosts.'''
        # params were: hosts, ips
        for host_dpid in self.topo.hosts():
            host = self.nodes[host_dpid]
            hintf = host.intfs[0]
            host.setIP(hintf, self.topo.ip(host_dpid),
                       '/' + str(self.cparams.subnet_size))
            host.setDefaultRoute(hintf)
            # You're low priority, dude!
            quietRun('renice +18 -p ' + repr(host.pid))
            lg.info('%s ', host.name)
        lg.info('\n')

    def build(self):
        '''Build mininet.

        At the end of this function, everything should be connected and up.
        '''
        if self.cleanup:
            pass # cleanup
        # validate topo?
        lg.info('*** Adding controller\n')
        self._add_controller(self.controller)
        lg.info('*** Creating network\n')
        lg.info('*** Adding hosts:\n')
        for host in sorted(self.topo.hosts()):
            self._add_host(host)
            lg.info('0x%x ' % host)
        lg.info('\n*** Adding switches:\n')
        for switch in sorted(self.topo.switches()):
            self._add_switch(switch)
            lg.info('0x%x ' % switch)
        lg.info('\n*** Adding edges:\n')
        for src, dst in sorted(self.topo.edges()):
            self._add_link(src, dst)
            lg.info('(0x%x, 0x%x) ' % (src, dst))
        lg.info('\n')

        if self.in_namespace:
            lg.info('*** Configuring control network\n')
            self._configureControlNetwork()

        lg.info('*** Configuring hosts\n')
        self._config_hosts()

        if self.xterms:
            self.start_xterms()
        if self.auto_set_macs:
            self.set_macs()
        if self.auto_static_arp:
            self.static_arp()

    def switch_nodes(self):
        '''Return switch nodes.'''
        return [self.nodes[dpid] for dpid in self.topo.switches()]

    def host_nodes(self):
        '''Return host nodes.'''
        return [self.nodes[dpid] for dpid in self.topo.hosts()]

    def start_xterms(self):
        '''Start an xterm for each node in the topo.'''
        lg.info("*** Running xterms on %s\n" % os.environ['DISPLAY'])
        cleanUpScreens()
        self.terms += makeXterms(self.controllers.values(), 'controller')
        self.terms += makeXterms(self.switch_nodes(), 'switch')
        self.terms += makeXterms(self.host_nodes(), 'host')

    def stop_xterms(self):
        '''Kill each xterm.'''
        # Kill xterms
        for term in self.terms:
            os.kill(term.pid, signal.SIGKILL)
        cleanUpScreens()

    def set_macs(self):
        '''Set MAC addrs to correspond to datapath IDs on hosts.

        Assume that the host only has one interface.
        '''
        for dpid in self.topo.hosts():
            host_node = self.nodes[dpid]
            host_node.setMAC(host_node.intfs[0], dpid)

    def static_arp(self):
        '''Add all-pairs ARP entries to remove the need to handle broadcast.'''
        for src in self.topo.hosts():
            src_node = self.nodes[src]
            for dst in self.topo.hosts():
                if src != dst:
                    src_node.setARP(dst, dst)

    def start(self):
        '''Start controller and switches\n'''
        lg.info('*** Starting controller\n')
        for cnode in self.controllers.values():
            cnode.start()
        lg.info('*** Starting %s switches\n' % len(self.topo.switches()))
        for switch_dpid in self.topo.switches():
            switch = self.nodes[switch_dpid]
            #lg.info('switch = %s' % switch)
            lg.info('0x%x ' % switch_dpid)
            switch.start(self.controllers)
        lg.info('\n')

    def stop(self):
        '''Stop the controller(s), switches and hosts\n'''
        if self.terms:
            lg.info('*** Stopping %i terms\n' % len(self.terms))
            self.stop_xterms()
        lg.info('*** Stopping %i hosts\n' % len(self.topo.hosts()))
        for host_dpid in self.topo.hosts():
            host = self.nodes[host_dpid]
            lg.info('%s ' % host.name)
            host.terminate()
        lg.info('\n')
        lg.info('*** Stopping %i switches\n' % len(self.topo.switches()))
        for switch_dpid in self.topo.switches():
            switch = self.nodes[switch_dpid]
            lg.info('%s' % switch.name)
            switch.stop()
        lg.info('\n')
        lg.info('*** Stopping controller\n')
        for cnode in self.controllers.values():
            cnode.stop()
        lg.info('*** Test complete\n')

    def run(self, test, **params):
        '''Perform a complete start/test/stop cycle.'''
        self.start()
        lg.info('*** Running test\n')
        result = getattr(self, test)(**params)
        self.stop()
        return result

    @staticmethod
    def _parse_ping(pingOutput):
        '''Parse ping output and return packets sent, received.'''
        r = r'(\d+) packets transmitted, (\d+) received'
        m = re.search(r, pingOutput)
        if m == None:
            lg.error('*** Error: could not parse ping output: %s\n' %
                     pingOutput)
            exit(1)
        sent, received = int(m.group(1)), int(m.group(2))
        return sent, received

    def ping(self, hosts = None):
        '''Ping between all specified hosts.

        @param hosts list of host DPIDs
        @return ploss packet loss percentage
        '''
        #self.start()
        # check if running - only then, start?
        packets = 0
        lost = 0
        ploss = None
        if not hosts:
            hosts = self.topo.hosts()
        lg.info('*** Ping: testing ping reachability\n')
        for node_dpid in hosts:
            node = self.nodes[node_dpid]
            lg.info('%s -> ' % node.name)
            for dest_dpid in hosts:
                dest = self.nodes[dest_dpid]
                if node != dest:
                    result = node.cmd('ping -c1 ' + dest.IP())
                    sent, received = self._parse_ping(result)
                    packets += sent
                    if received > sent:
                        lg.error('*** Error: received too many packets')
                        lg.error('%s' % result)
                        node.cmdPrint('route')
                        exit(1)
                    lost += sent - received
                    lg.info(('%s ' % dest.name) if received else 'X ')
            lg.info('\n')
            ploss = 100 * lost / packets
        lg.info("*** Results: %i%% dropped (%d/%d lost)\n" %
                (ploss, lost, packets))
        return ploss

    def ping_all(self):
        '''Ping between all hosts.

        @return ploss packet loss percentage
        '''
        return self.ping()

    def ping_pair(self):
        '''Ping between first two hosts, useful for testing.

        @return ploss packet loss percentage
        '''
        hosts_sorted = sorted(self.topo.hosts())
        hosts = [hosts_sorted[0], hosts_sorted[1]]
        return self.ping(hosts = hosts)

    @staticmethod
    def _parseIperf(iperfOutput):
        '''Parse iperf output and return bandwidth.

        @param iperfOutput string
        @return result string
        '''
        r = r'([\d\.]+ \w+/sec)'
        m = re.search(r, iperfOutput)
        if m:
            return m.group(1)
        else:
            raise Exception('could not parse iperf output')

    def iperf(self, hosts = None, l4_type = 'TCP', udp_bw = '10M',
              verbose = False):
        '''Run iperf between two hosts.

        @param hosts list of host DPIDs; if None, uses opposite hosts
        @param l4_type string, one of [TCP, UDP]
        @param verbose verbose printing
        @return results two-element array of server and client speeds
        '''
        if not hosts:
            hosts_sorted = sorted(self.topo.hosts())
            hosts = [hosts_sorted[0], hosts_sorted[-1]]
        else:
            assert len(hosts) == 2
        host0 = self.nodes[hosts[0]]
        host1 = self.nodes[hosts[1]]
        lg.info('*** Iperf: testing ' + l4_type + ' bandwidth between ')
        lg.info("%s and %s\n" % (host0.name, host1.name))
        host0.cmd('killall -9 iperf')
        iperf_args = 'iperf '
        bw_args = ''
        if l4_type == 'UDP':
            iperf_args += '-u '
            bw_args = '-b ' + udp_bw + ' '
        elif l4_type != 'TCP':
            raise Exception('Unexpected l4 type: %s' % l4_type)
        server = host0.cmd(iperf_args + '-s &')
        if verbose:
            lg.info('%s\n' % server)
        client = host1.cmd(iperf_args + '-t 5 -c ' + host0.IP() + ' ' +
                           bw_args)
        if verbose:
            lg.info('%s\n' % client)
        server = host0.cmd('killall -9 iperf')
        if verbose:
            lg.info('%s\n' % server)
        result = [self._parseIperf(server), self._parseIperf(client)]
        if l4_type == 'UDP':
            result.insert(0, udp_bw)
        lg.info('*** Results: %s\n' % result)
        return result

    def iperf_udp(self, udp_bw = '10M'):
        '''Run iperf UDP test.'''
        return self.iperf(l4_type = 'UDP', udp_bw = udp_bw)

    def interact(self):
        '''Start network and run our simple CLI.'''
        self.start()
        result = MininetCLI(self)
        self.stop()
        return result


class MininetCLI(object):
    '''Simple command-line interface to talk to nodes.'''
    cmds = ['?', 'help', 'nodes', 'net', 'sh', 'ping_all', 'exit', \
            'ping_pair', 'iperf', 'iperf_udp', 'intfs', 'dump']

    def __init__(self, mininet):
        self.mn = mininet
        self.nodemap = {} # map names to Node objects
        for node in self.mn.nodes.values():
            self.nodemap[node.name] = node
        for cname, cnode in self.mn.controllers.iteritems():
            self.nodemap[cname] = cnode
        self.nodelist = self.nodemap.values()
        self.run()

    # Disable pylint "Unused argument: 'arg's'" messages.
    # Each CLI function needs the same interface.
    # pylint: disable-msg=W0613

    # Commands
    def help(self, args):
        '''Semi-useful help for CLI.'''
        help_str = 'Available commands are:' + str(self.cmds) + '\n' + \
                   'You may also send a command to a node using:\n' + \
                   '  <node> command {args}\n' + \
                   'For example:\n' + \
                   '  mininet> h0 ifconfig\n' + \
                   '\n' + \
                   'The interpreter automatically substitutes IP ' + \
                   'addresses\n' + \
                   'for node names, so commands like\n' + \
                   '  mininet> h0 ping -c1 h1\n' + \
                   'should work.\n' + \
                   '\n\n' + \
                   'Interactive commands are not really supported yet,\n' + \
                   'so please limit commands to ones that do not\n' + \
                   'require user interaction and will terminate\n' + \
                   'after a reasonable amount of time.\n'
        print(help_str)

    def nodes(self, args):
        '''List all nodes.'''
        lg.info('available nodes are: \n%s\n',
                ' '.join([node.name for node in sorted(self.nodelist)]))

    def net(self, args):
        '''List network connections.'''
        for switch_dpid in self.mn.topo.switches():
            switch = self.mn.nodes[switch_dpid]
            lg.info('%s <->', switch.name)
            for intf in switch.intfs:
                node = switch.connection[intf]
                lg.info(' %s' % node.name)
            lg.info('\n')

    def sh(self, args):
        '''Run an external shell command'''
        call(['sh', '-c'] + args)

    def ping_all(self, args):
        '''Ping between all hosts.'''
        self.mn.ping_all()

    def ping_pair(self, args):
        '''Ping between first two hosts, useful for testing.'''
        self.mn.ping_pair()

    def iperf(self, args):
        '''Simple iperf TCP test between two hosts.'''
        self.mn.iperf()

    def iperf_udp(self, args):
        '''Simple iperf UDP test between two hosts.'''
        udp_bw = args[0] if len(args) else '10M'
        self.mn.iperf_udp(udp_bw)

    def intfs(self, args):
        '''List interfaces.'''
        for node in self.mn.nodes.values():
            lg.info('%s: %s\n' % (node.name, ' '.join(node.intfs)))

    def dump(self, args):
        '''Dump node info.'''
        for node in self.mn.nodes.values():
            lg.info('%s\n' % node)

    # Re-enable pylint "Unused argument: 'arg's'" messages.
    # pylint: enable-msg=W0613

    def run(self):
        '''Read and execute commands.'''
        lg.warn('*** Starting CLI:\n')
        while True:
            lg.warn('mininet> ')
            input_line = sys.stdin.readline()
            if input_line == '':
                break
            if input_line[-1] == '\n':
                input_line = input_line[:-1]
            cmd = input_line.split(' ')
            first = cmd[0]
            rest = cmd[1:]
            if first in self.cmds and hasattr(self, first):
                getattr(self, first)(rest)
            elif first in self.nodemap and rest != []:
                node = self.nodemap[first]
                # Substitute IP addresses for node names in command
                rest = [self.nodemap[arg].IP() if arg in self.nodemap else arg
                        for arg in rest]
                rest = ' '.join(rest)
                # Interactive commands don't work yet, and
                # there are still issues with control-c
                lg.warn('*** %s: running %s\n' % (node.name, rest))
                node.sendCmd(rest)
                while True:
                    try:
                        done, data = node.monitor()
                        lg.info('%s\n' % data)
                        if done:
                            break
                    except KeyboardInterrupt:
                        node.sendInt()
            elif first == '':
                pass
            elif first in ['exit', 'quit']:
                break
            elif first == '?':
                self.help(rest)
            else:
                lg.error('CLI: unknown node or command: < %s >\n' % first)
            #lg.info('*** CLI: command complete\n')
        return 'exited by user command'
