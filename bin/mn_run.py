#!/usr/bin/env python
'''Mininet runner

@author Brandon Heller (brandonh@stanford.edu)
'''

from optparse import OptionParser
import time

try:
    from ripcord.dctopo import TreeTopo, FatTreeTopo, VL2Topo
    USE_RIPCORD = True
except ImportError:
    USE_RIPCORD = False

from mininet.logging_mod import lg, set_loglevel, LEVELS
from mininet.net import Mininet, init
from mininet.node import KernelSwitch, Host, Controller, ControllerParams, NOX
from mininet.node import RemoteController
from mininet.topo import SingleSwitchTopo, LinearTopo, SingleSwitchReversedTopo

# built in topologies, created only when run
TOPO_DEF = 'minimal'
TOPOS = {'minimal' :   (lambda: SingleSwitchTopo(k = 2)),
         'reversed' :  (lambda: SingleSwitchReversedTopo(k = 2)),
         'single4' :   (lambda: SingleSwitchTopo(k = 4)),
         'single100' : (lambda: SingleSwitchTopo(k = 100)),
         'linear2' :   (lambda: LinearTopo(k = 2)),
         'linear100' : (lambda: LinearTopo(k = 100))}
if USE_RIPCORD:
    TOPOS_RIPCORD = {
         'tree16' :   (lambda: TreeTopo(depth = 3, fanout = 4)),
         'tree64' :   (lambda: TreeTopo(depth = 4, fanout = 4)),
         'tree1024' : (lambda: TreeTopo(depth = 3, fanout = 32)),
         'fattree4' : (lambda: FatTreeTopo(k = 4)),
         'fattree6' : (lambda: FatTreeTopo(k = 6)),
         'vl2'      : (lambda: VL2Topo(da = 4, di = 4))}
    TOPOS.update(TOPOS_RIPCORD)

SWITCH_DEF = 'kernel'
SWITCHES = {'kernel' : KernelSwitch}

HOST_DEF = 'process'
HOSTS = {'process' : Host}

CONTROLLER_DEF = 'ref'
# a and b are the name and inNamespace params.
CONTROLLERS = {'ref' : Controller,
               'nox_dump' : lambda a, b: NOX(a, b, 'packetdump'),
               'nox_pysw' : lambda a, b: NOX(a, b, 'pyswitch'),
               'remote' : lambda a, b: None,
               'none' :     lambda a, b: None}

# optional tests to run
TESTS = ['cli', 'build', 'ping_all', 'ping_pair', 'iperf', 'all', 'iperf_udp']

def add_dict_option(opts, choices_dict, default, name, help_str = None):
    '''Convenience function to add choices dicts to OptionParser.
    
    @param opts OptionParser instance
    @param choices_dict dictionary of valid choices, must include default
    @param default default choice key
    @param name long option name
    @param help string
    '''
    if default not in choices_dict:
        raise Exception('Invalid  default %s for choices dict: %s' %
                        (default, name))
    if not help_str:
        help_str = '[' + ' '.join(choices_dict.keys()) + ']'
    opts.add_option('--' + name,
                    type = 'choice',
                    choices = choices_dict.keys(),
                    default = default,
                    help = help_str)


class MininetRunner(object):
    '''Build, setup, and run Mininet.'''

    def __init__(self):
        '''Init.'''
        self.options = None
        
        self.parse_args()
        self.setup()
        self.begin()

    def parse_args(self):
        '''Parse command-line args and return options object.
        
        @return opts parse options dict
        '''
        opts = OptionParser()
        add_dict_option(opts, TOPOS, TOPO_DEF, 'topo')
        add_dict_option(opts, SWITCHES, SWITCH_DEF, 'switch')
        add_dict_option(opts, HOSTS, HOST_DEF, 'host')
        add_dict_option(opts, CONTROLLERS, CONTROLLER_DEF, 'controller')

        opts.add_option('--test', type = 'choice', choices = TESTS,
                        default = TESTS[0],
                        help = '[' + ' '.join(TESTS) + ']')
        opts.add_option('--xterms', '-x', action = 'store_true',
                        default = False, help = 'spawn xterms for each node')
        opts.add_option('--mac', action = 'store_true',
                        default = False, help = 'set MACs equal to DPIDs')
        opts.add_option('--arp', action = 'store_true',
                        default = False, help = 'set all-pairs ARP entries')
        opts.add_option('--verbosity', '-v', type = 'choice',
                        choices = LEVELS.keys(), default = 'info',
                        help = '[' + ' '.join(LEVELS.keys()) + ']')
        opts.add_option('--ip', type = 'string', default = '127.0.0.1',
                        help = '[ip address as a dotted decimal string for a'
                        'remote controller]')
        opts.add_option('--port', type = 'string', default = 6633,
                        help = '[port integer for a listening remote'
                        ' controller]')
        self.options = opts.parse_args()[0]

    def setup(self):
        '''Setup and validate environment.'''

        # set logging verbosity
        set_loglevel(self.options.verbosity)

        # validate environment setup
        init()

        # check for invalid combinations
        if self.options.controller == 'ref' and \
            (('fattree' in self.options.topo) or ('vl2' in self.options.topo)):
            raise Exception('multipath topos require multipath-capable '
                            'controller.')

    def begin(self):
        '''Create and run mininet.'''

        start = time.time()

        topo = TOPOS[self.options.topo]() # build topology object
        switch = SWITCHES[self.options.switch]
        host = HOSTS[self.options.host]
        controller = CONTROLLERS[self.options.controller]
        if self.options.controller == 'remote':
            controller = lambda a, b: RemoteController(a, b,
                             ip_address = self.options.ip,
                             port = self.options.port)

        controller_params = ControllerParams(0x0a000000, 8) # 10.0.0.0/8
        xterms = self.options.xterms
        mac = self.options.mac
        arp = self.options.arp
        mn = Mininet(topo, switch, host, controller, controller_params,
                     xterms = xterms, auto_set_macs = mac,
                     auto_static_arp = arp)

        test = self.options.test
        if test != 'build':
            if test == 'cli':
                mn.interact()
            elif test == 'all':
                mn.start()
                mn.ping()
                mn.iperf()
                mn.stop()
            else:
                mn.run(test)

        elapsed = float(time.time() - start)
        print ('completed in %0.3f seconds' % elapsed)


if __name__ == "__main__":
    MininetRunner()
