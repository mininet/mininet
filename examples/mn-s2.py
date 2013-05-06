#!/usr/bin/env python

"""
Mininet runner
author: Brandon Heller (brandonh@stanford.edu)

To see options:
  sudo mn -h

Example to pull custom params (topo, switch, etc.) from a file:
  sudo mn --custom ~/mininet/custom/custom_example.py
"""

from optparse import OptionParser
import os
import sys
import time

# Fix setuptools' evil madness, and open up (more?) security holes
if 'PYTHONPATH' in os.environ:
    sys.path = os.environ[ 'PYTHONPATH' ].split( ':' ) + sys.path

from mininet.clean import cleanup
from mininet.cli import CLI
from mininet.log import lg, LEVELS, info
from mininet.net import Mininet, MininetWithControlNet, VERSION
from mininet.node import ( Host, CPULimitedHost, Controller, OVSController,
                           NOX, RemoteController, UserSwitch, OVSKernelSwitch,
                           OVSLegacyKernelSwitch )
from mininet.link import Link, TCLink
from mininet.topo import SingleSwitchTopo, LinearTopo, SingleSwitchReversedTopo, Topo
from mininet.topolib import TreeTopo
from mininet.util import custom, customConstructor, irange
from mininet.util import buildTopo

TOPODEF = 'minimal'
TOPOS = { 'minimal': lambda: SingleSwitchTopo( k=2 ),
          'linear': LinearTopo,
          'reversed': SingleSwitchReversedTopo,
          'single': SingleSwitchTopo,
          'tree': TreeTopo 
        }

SWITCHDEF = 'ovsk'
SWITCHES = { 'user': UserSwitch,
             'ovsk': OVSKernelSwitch,
             'ovsl': OVSLegacyKernelSwitch }

HOSTDEF = 'proc'
HOSTS = { 'proc': Host,
          'rt': custom( CPULimitedHost, sched='rt' ),
          'cfs': custom( CPULimitedHost, sched='cfs' ) }

CONTROLLERDEF = 'ovsc'
CONTROLLERS = { 'ref': Controller,
                'ovsc': OVSController,
                'nox': NOX,
                'remote': RemoteController,
                'none': lambda name: None }

LINKDEF = 'default'
LINKS = { 'default': Link,
          'tc': TCLink }

#preconfigured services
#service description dictionary can have following sets of keys:
#{cmd_start, [start_custom_opts], need_stop = False}
#{cmd_start, [start_custom_opts], need_stop = True, cmd_stop = None }=> (killing by pid)
#{cmd_start, [start_custom_opts], need_stop = True, cmd_stop, [stop_custom_opts]}

SERVICES = { 'dhcpd': { 'cmd_start': 'dhcpd', 
                        'start_custom_opts': '--no-pid -cf /etc/dhcp/dhcpd.mininet.conf',
                        'cmd_stop': None,
                        'need_stop': True
                        },
             #'dhclient': {  'cmd_start': 'dhclient -rv ; dhclient -v', 
             'dhclient': {  'cmd_start': 'dhclient -v', 
                            'need_stop': False
#			    'cmd_stop': 'dhclient -x'
			 } 
}

#switch s0 supposed to handle all 'special' service hosts 'hs#'
#still one can define services on other hosts, no restrictions
#switch s0 is also a root switch for other switches
class WiFiTopo( Topo ):
    "Topology for one Mininet segment for WiFi app bench"

    def __init__( self, N, S, **params ):

        Topo.__init__( self, **params )

        #switch = self.addSwitch('s0',dpid=str(FIRST_IP))
        switch = self.addSwitch('s0')
        hs = self.addHost( 'hs%s' % '0' )
        self.addLink(hs, switch)

        for sw in irange( 1, S):
            hosts = [ self.addHost( 'h%s' % h ) for h in irange( (sw-1)*N+1, sw*N ) ]
            #switchS = self.addSwitch('s'+str(sw),dpid=str(sw+FIRST_IP)) 
            switchS = self.addSwitch('s'+str(sw)) 
            print(switchS)
            self.addLink(switch, switchS)
            for host in hosts:
                self.addLink(host, switchS)
                #statistically emulated wifi link
                #typical 802.11g wifi router link params:
                #bandwidth 17Mbps, delay 2ms, loss 1%
                #self.addLink(host, switchS, bw=17, delay='2ms', loss=1)


#wrapper class for Mininet to incorporate services launcher
#'example' style solution only! 
#Normaly ought to be implemented through core classes. Not wrapper!
#
class wrpMininet(Mininet):
    def __init__(self, *pargs, **kwargs):
        Mininet.__init__(self, *pargs, **kwargs)
        self.services = {}

    def start( self ):
        Mininet.start(self)
        #services unrolling
        self.start_services()

    def stop( self ):
        #services shutdown
        self.stop_services()
        Mininet.stop(self)

    def add_preconf_service(self, priority, hostname, service_id):
        try:
            p = int(priority)
            h = str(hostname)
        except ValueError:
            print >> sys.stderr, "Wrong priority or hostname argument"
            return False
        if h not in self.nameToNode.keys():
            print >> sys.stderr, "Unknown host %s" % h 
            return False
        if service_id not in SERVICES.keys():
            print >> sys.stderr, "Unknown preconfigured service %s" % str(service_id)
            return False
        return self.do_add_service(p, h, SERVICES[service_id])

    def add_service(self, priority, hostname, service_args_dict):
        try:
            p = int(priority)
            h = str(hostname)
        except ValueError:
            print >> sys.stderr, "Wrong priority or hostname argument"
            return False
        if h not in self.nameToNode.keys():
            print >> sys.stderr, "Unknown host %s" % h 
            return False
        #obscure service description dictionary logic check
        if 'cmd_start' not in service_args_dict.keys():
            print >> sys.stderr, "Customized service for %s lacks cmd_start string" % h
            return False
        if 'need_stop' not in service_args_dict.keys():
            print >> sys.stderr, "Customized service for %s lacks need_stop bool" % h
            return False
        if not service_args_dict['need_stop']:
            return self.do_add_service(p, h, service_args_dict)
        #need_stop == False
        if 'cmd_stop' not in service_args_dict.keys():
            print >> sys.stderr, "Customized service for %s lacks cmd_stop bool" % h
            return False
        return self.do_add_service(p, h, service_args_dict)

    def do_add_service(self, prio, host, service_args_dict):
        #services is a dictionary of lists by priority
        #each list contains dictionaries, describing particular service 
        #on particular host instance
        if prio not in self.services.keys():
            self.services[prio] = []
        #prepare entry
        s_entry = service_args_dict.copy()
        s_entry['host'] = host
        s_entry['pid'] = None
        self.services[prio].append(s_entry)

    def start_services(self):
        for p in sorted(self.services):
            for hsi_d in self.services[p]:
                h = self.nameToNode[hsi_d['host']]
                cmdl = [ hsi_d['cmd_start'] ]
                if 'start_custom_opts' in hsi_d.keys():
                    cmdl.append(hsi_d['start_custom_opts'])
                #no pid back yet!
                h.cmd(cmdl)
	    time.sleep(2)
	#update IPs of all hosts
	#very dirty fix
	for h in self.hosts:
	    h.defaultIntf().updateIP()
	

    def stop_services(self):
        for p in sorted(self.services):
            for hsi_d in self.services[p]:
                if not hsi_d['need_stop']:
                    continue
                h = self.nameToNode[hsi_d['host']]
		print "Host -- ", hsi_d['host']
                cmdl = [ hsi_d['cmd_stop'] ]
                if 'stop_custom_opts' in hsi_d.keys():
                    cmdl.append(hsi_d['stop_custom_opts'])
                #no pid back yet!
                h.cmd(cmdl)

class MininetRunner( object ):
    "Build, setup, and run Mininet."
    def __init__( self ):
        "Init."
        #N -- number of "wifi" hosts per "wifi" switch
        #S -- number of "wifi" switches sitting on root switch
        self.N = 2
        self.S = 3

        self.options = None
        self.args = None  # May be used someday for more CLI scripts
        self.validate = None

#        self.parseArgs()
#        self.setup()
        self.begin()

    def setCustom( self, name, value ):
        "Set custom parameters for MininetRunner."
        if name in ( 'topos', 'switches', 'hosts', 'controllers' ):
            # Update dictionaries
            param = name.upper()
            globals()[ param ].update( value )
        elif name == 'validate':
            # Add custom validate function
            self.validate = value
        else:
            # Add or modify global variable or class
            globals()[ name ] = value

    def parseCustomFile( self, fileName ):
        "Parse custom file and add params before parsing cmd-line options."
        customs = {}
        if os.path.isfile( fileName ):
            execfile( fileName, customs, customs )
            for name, val in customs.iteritems():
                self.setCustom( name, val )
        else:
            raise Exception( 'could not find custom file: %s' % fileName )

    def begin( self ):
        "Create and run mininet."

#        if self.options.clean:
#            cleanup()
#            exit()

        start = time.time()

 #       topo = buildTopo( TOPOS, self.options.topo )
        #3 wifi handling switches with 2 clients each
        topo = WiFiTopo( N = self.N, S = self.S )
        switch = customConstructor( SWITCHES, SWITCHDEF )
        host = customConstructor( HOSTS, HOSTDEF )
        controller = customConstructor( CONTROLLERS, CONTROLLERDEF )
        link = customConstructor( LINKS, LINKDEF )

        inNamespace = False
        #Net = MininetWithControlNet if inNamespace else Mininet
        Net = wrpMininet
        ipBase = '10.0.0.0/8'
	listenPort = 6634 

        mn = Net( topo=topo,
                  switch=switch, host=host, controller=controller,
                  link=link,
                  ipBase=ipBase,
                  inNamespace=inNamespace,
                  listenPort=listenPort )

#Add services here
        mn.add_preconf_service(1, 'hs0', 'dhcpd')
        
        for swi in irange( 1, self.S):
            hl = [ ('h%s' % h ) for h in irange((swi - 1) * self.N + 1, swi * self.N) ]
            for hn in hl:
                mn.add_preconf_service(2, hn, 'dhclient')

        mn.start()
	CLI(mn)
        mn.stop()

        elapsed = float( time.time() - start )
        info( 'completed in %0.3f seconds\n' % elapsed )


if __name__ == "__main__":
    MininetRunner()

