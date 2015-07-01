#!/usr/bin/python

"""
Provides webservices to build, destroy, and recreate networks

"""
import os
import sys
libdir = os.path.abspath(os.path.dirname(sys.argv[0]))
sys.path.insert(0, libdir+'/lib')

import re
import socket
import fcntl
import struct
import xml.etree.ElementTree as ET
from mininet.cli import CLI
from mininet.net import Mininet
from mininet.util import quietRun
#from mininet.examples.cluster import MininetCluster, SwitchBinPlacer, RemoteHost, RemoteLink, RemoteOVSSwitch
from mininet.node import RemoteController, OVSSwitch, Host
from mininet import CustomLink
from mininet.log import setLogLevel
from mininet.link import Intf, Link
#from subprocess import check_call
import subprocess 
import urllib

# import bottle framework
from bottle import route, run, template, request

setLogLevel( 'info' )

# gets the ipaddress of an interface
# used to figure out which ip we should run bottle on
def get_ip_address(ifname):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    return socket.inet_ntoa(fcntl.ioctl(
        s.fileno(),
        0x8915,  # SIOCGIFADDR
        struct.pack('256s', ifname[:15])
    )[20:24])

# get our servers from the config file
def get_servers():
    servers = []
    config  = ET.parse('conf/mininet_webservice.xml').getroot()
    
    for server in config.findall('server'):
        servers.append(server.get('name'))

    return servers
servers = get_servers()

# make our ofp dict (used for parsing dpctl dump-flows)
def get_ofp_dict():
    ofp_dict = { 'matches': {} }
    config  = ET.parse('conf/ofp_dict.xml').getroot()
    # get our matches
    for match in config.findall('match'):
        ofp_dict['matches'][match.text] = 1

    return ofp_dict
ofp_dict = get_ofp_dict()

# init topology and network
net = Mininet( 
    topo=None,
    build=False,
    switch=OVSSwitch,
    controller=RemoteController,
    link=Link,
    host=Host
)
# start is_running to false and server index at 0
is_running = False
server_index = 0
method_list = {}

# pretty dumb round robining but good enough for meow, mininet comes with
# some balancing classes but at a glance they seem to only work if you build
# your network with a topo class. need to dig into that a bit further
def get_next_server():
    global server_index
    current_index = server_index % len(servers)
    server = servers[current_index]
    server_index += 1
    return server

def main():

    # provides a consistent way to return data via webservices
    def format_results( res, err=None ):
        error_bool = True if(err) else False
        return { 
            'results':   res,
            'error':     error_bool,
            'error_msg': err
        }

    # PARAM CHECKS - special param specific checks to perform
    def node_exists( msg="Node, {0}, does not exist", success=True ):
        if( success == False ):
            msg="Node, {0}, already exist"
        def wrapper( name ):
            exists = None
            try:
                net.get( name )
                exists = True
            except:
                exists = False

            if( exists != success ):
                return (True, msg.format(name))

            return (False, "")
        var_str = " " if(success) else " does not "
        wrapper.__descr__ = "ensures node"+var_str+"exist"
        return wrapper

    def link_exists( msg="Link, {0}, does not exist", success=True ):
        if( success == False ):
            msg="Link, {0}, already exist"
        def wrapper( name ):
            exists = None
            link = net.getLink( name )
            if(link):
                exists = True
            else:
                exists = False

            if( exists != success ):
                return (True, msg.format(name))

            return (False, "")
        var_str = " " if(success) else " does not "
        wrapper.__descr__ = "ensures link"+var_str+"exist"
        return wrapper

    # takes in a validator grabs the method_name and method_description keys
    # to build a help message to print to the user when /help is executed
    def create_method_help_obj( validators ):
        global method_list
       
        # grab our name and description and remove them from the validator dict
        method_name        = validators.pop('method_name', None)
        method_description = validators.pop('method_description', None)

        # make sure they are defined
        if(method_name is None):
            print "You must provide a method_name along with the validator for the /help method!"
            sys.exit(1)
        if(method_description is None):
            print "You must provide a method_description along with the validator for the /help method!"
            sys.exit(1)

        method_list[method_name] = {}
        method_list[method_name]['description'] = method_description
        method_list[method_name]['parameters']  = []

        for param in validators:
            parameter = {}
            validator = validators[param]
            parameter['name']     = param
            parameter['required'] = validator.get('required', False)

            if(validator.get('pattern', False)):
                parameter['pattern'] = validator.get('pattern')

            if(validator.get('type', False)):
                parameter['type'] = validator.get('type')

            if(validator.get('checks', False)):
                checks = validator.get('checks');
                parameter['checks'] = []
                for check in checks:
                    try:
                        parameter['checks'].append(check.__descr__)
                    except:
                        print "Must provide __descr__ for checks!"
                        sys.exit(1)
            method_list[method_name]['parameters'].append(parameter)

        method_list[method_name]['parameters'] = sorted( method_list[method_name]['parameters'], key=lambda k: k['name']) 

        return validators


    # special decorator that takes in kwargs where the key is the parameter
    # and the value is an object representing the validation it should do to the 
    # parameter
    def validate_params( **kwargs ):
        validators = create_method_help_obj(kwargs)
        def validate_params_decorator(func):
            def wrapper(*args, **kwargs):
                validated_args = {}
                for param in validators:
                    validator = validators[param]
                    checks    = validator.get('checks', [])
                    default   = validator.get('default', None)
                    value     = request.params.get(param, default)

                    # check if the param was required
                    if(validator.get('required', False) and value == None ):
                        return format_results( None, "Parameter, {0}, is required".format(param) )

                    # only do further validation if it's not required
                    if(value != None):
                        # if the parameter needs to match a particular pattern make sure it does
                        if( validator.get('pattern', False) ):
                            pattern = validator.get('pattern')
                            regex   = re.compile(pattern)
                            if(not regex.match(value) ): 
                                return format_results( None, "Parameter, {0}, must match pattern, {1}".format(param, pattern) )

                        # if a type is set try to convert to the type otherwise send error
                        if( validator.get('type', False) ):
                            if( validator.get('type') == 'string' ):
                                try: 
                                    value = str(value)
                                except Exception as e:
                                    return format_results( None, "Error converting {0} to string: {1}".format(value, e))
                            if( validator.get('type') == 'integer' ):
                                try: 
                                    value = int(value)
                                except Exception as e:
                                    return format_results( None, "Error converting {0} to integer: {1}".format(value, e))


                        # if the param has any special check perform them now
                        for check in checks:
                            err, msg = check( value )
                            if(err):
                                return format_results( None, msg )

                    # if we've gotten here the param is good so add it to our validated params
                    validated_args[param] = value


                return func(validated_args)
            return wrapper
        return validate_params_decorator

    @route('/add_vlan')
    @validate_params(
        method_name = 'add_vlan',
        method_description = 'Creates a new vlan interface via vconfig',
        host   = { 'required': True, 'checks': [ node_exists() ] },
        vlan   = { 'required': True },
        intf   = { 'required': True },
        ip     = {},
        mask   = {}
    )
    def add_vlan( params ):
        host = params.get('host')
        vlan = int(params.get('vlan'))
        intf = params.get('intf')
        ip   = params.get('ip')
        mask = params.get('mask')

        # get host
        host = net.get(host)
        intf = host.nameToIntf[ intf ]
        intf_name = "%s-%s" % (str(host.id), str(host.ports[ intf ]))

        if(vlan > 0 and vlan < 4096):
            # add vlan
            out, err, code = host.pexec('vconfig add {0} {1}'.format(intf_name, vlan))
            if(code):
                return format_results(out, err)

        # add ip addr if it was passed in
        if( (ip is not None) and (mask is not None) ):
            return add_ip_addr({
                'ip':   ip,
                'mask': mask,
                'vlan': vlan,
                'intf': intf,
                'host': host.name
            })
        return format_results( [{'name': "{0}.{1}".format(intf_name, vlan)}] )


    @route('/ifconfig')
    @validate_params(
        method_name = 'ifconfig',
        method_description = 'Runs ifconfig on given node',
        node   = { 'required': True, 'checks': [ node_exists() ] }
    )	
    def ifconfig( params ):
        node = params.get('node')

        # get host
        node = net.get(node)

        # add vlan
        out, err, code = node.pexec('ifconfig')
        if(code):
             return format_results(out, err)

        return format_results( [{'ifconfig': out.split('\n') }] )


    @route('/add_ip_addr')
    @validate_params(
        method_name = 'add_ip_addr',
        method_description = 'Adds an ip address to an interface via ifconfig',
        host   = { 'required': True, 'checks': [ node_exists() ] },
        intf   = { 'required': True },
        ip     = { 'required': True },
        mask   = { 'required': True },
        vlan   = {}
    )
    def add_ip_addr( params ):
        host = params.get('host')
        intf = params.get('intf')
        ip   = params.get('ip')
        mask = params.get('mask')
        vlan = int(params.get('vlan'))

        host = net.get(host)

        intf = host.nameToIntf[ intf ]
        intf_name = "%s-%s" % (str(host.id), str(host.ports[ intf ]))
        # append vlan on end of intf is passed in
        if(vlan is not None and vlan > 0 and vlan < 4096): intf_name = intf_name + '.' + str(vlan)

        out, err, code = host.pexec('ifconfig {0} {1}/{2}'.format(intf_name, ip, mask))
        if(code):
             return format_results(out, err)

        return format_results( [{'name': "{0}".format(intf_name)}] )

    @route('/ping')
    @validate_params(
        method_name = 'ping',
        method_description = 'Sends a ping from a host to another host or ip and returns the results',
        src   = { 'required': True, 'checks': [ node_exists() ] },
        dst   = { 'required': True },
	count = { 'default': 5 },
	raw   = { 'default': False }
    )
    def ping( params ):
        if(not is_running):
            return format_results( None, "Can not ping a host when mininet is not running" )

	src   = params.get('src')
	dst   = params.get('dst')
	count = params.get('count')
	raw   = params.get('raw')

        host = net.get(src)

        out, err, code = host.pexec( "ping -c {0} {1}".format(count, dst) )
	if(err):
	    format_results(None, err)
	if(raw):
	    format_results(out, err)

	lines   = out.split('\n')
	results = { 'pings': [], 'stats': None }
	for line in lines:
            # capture a ping message
            capture = re.search('(\d+) bytes from (.*): icmp_seq=(\d+) ttl=(\d+) time=(.*) ms', line)
            if(capture):
		bytesSent = int(capture.group(1))
                src       = capture.group(2)
                icmp_seq  = int(capture.group(3))
		ttl       = int(capture.group(4))
		time      = float(capture.group(5))
                results['pings'].append({
		    'bytes': bytesSent,
                    'src': src,
                    'icmp_seq': icmp_seq,
                    'ttl': ttl,
                    'time_ms': time
                })

	    # capture a ping failure message
	    capture = re.search('From (.*) icmp_seq=(\d+) (.*)', line)
            if(capture):
            	src      = capture.group(1)
            	icmp_seq = int(capture.group(2))
		msg      = capture.group(3)
	    	results['pings'].append({
		    'src': src,
		    'msg': msg,
		    'icmp_seq': icmp_seq
		})

	    # capture the statistics message
            capture = re.search(
	        '(\d+) packets transmitted, (\d+) received, (?:\+(\d+) errors, )?(\d+)% packet loss, time (\d+)ms',
		line
	    )
            if(capture):
                tx_packets      = int(capture.group(1))
                rx_packets      = int(capture.group(2))
                errors          = int(capture.group(3)) if(capture.group(3) is not None) else 0
		packet_loss_pct = int(capture.group(4))
		time_ms         = int(capture.group(5))

                results['stats'] = {
		    'tx_packets': tx_packets,
		    'rx_packets': rx_packets,
		    'errors': errors,
		    'packet_loss_pct': packet_loss_pct,
		    'time_ms': time_ms
                }
        
	return format_results( results, err )


    @route('/flows')
    @validate_params(
        method_name = 'flows',
        method_description = 'Retrieve ofp flow mods for specified switches',
        switch = { 'checks': [ node_exists() ] }
    )
    def flows( params ):
        if(not is_running):
            return format_results( None, "Can not retrieve flow stats when mn is not running" )

        # pull out params
        switch_name = params.get('switch')

        switches = []
        if(switch_name):
            switches.append(net.get(switch_name))
        else:
            switches = net.switches 

        # this will convert the string blob returned by dump-flows into an object
        def parse_stats_and_matches(str):
            stats = { 'matches': {} }
            
            for kvp_str in str.split(','):
                # get rid of leading and trailing whitespace
                kvp_str = kvp_str.strip()
                # if kvp_str is now an empty string skip (this is a wildcard match)
                if(kvp_str == ""): continue
                # split on '=' to get our key and value for the attr
                kvp = kvp_str.split('=')

                # convert numbers to ints if we can
                try:
                    kvp[1] = int(kvp[1])
                except:
                    kvp[1] = kvp[1]

                if(kvp[0] in ofp_dict['matches']):
                    stats['matches'][kvp[0]] = kvp[1]
                else:
                    stats[kvp[0]] = kvp[1]
            return stats

        def parse_actions(str):
            actions = []
	    for kvp_str in str.split(','):
                # get rid of leading and trailing whitespace
                kvp_str = kvp_str.strip()

                # split on '=' to get our key and value for the attr
                kvp = kvp_str.split(':')
		
		if(len(kvp) < 2): continue

                # convert numbers to ints if we can
                try:
                    kvp[1] = int(kvp[1])
                except:
                    kvp[1] = kvp[1]

		actions.append({ kvp[0]: kvp[1] })

	    return actions

        # now loop through our switches getting their stats
        results = []
        for switch in switches:
            flow_txt = switch.dpctl('dump-flows')

            if(re.match("ovs-ofctl: (.*)? is not a bridge or a socket", flow_txt)):
                results.append({
                    'name': "{0}".format(switch),
                    'xid': None,
                    'flows': None,
                    'error': True,
                    'error_msg': flow_txt
                })
                continue
                
            # need to do some formatting to this awful string blob
            capture = re.search('NXST_FLOW reply \(xid=(.*)?\):(.*)', flow_txt, re.MULTILINE|re.DOTALL)

            #capture    = regex.search(flow_txt)
            xid        = capture.group(1)
            flows_blob = capture.group(2) 

            # remove leading and trailing newline characters
            flows_blob = flows_blob[1:]
            flows_blob = flows_blob[:-1]

            flows = []
            # if we have flows on the switch parse them
            if(flows_blob != ''):
                # split on new lines to get a flow
                for flow_blob in flows_blob.split('\r\n'):
                    # use regex to split the stats, matches, and actions
                    capture = re.search('(.*) actions=(.*)', flow_blob)
                    stats_matches_str = capture.group(1)
                    actions_str       = capture.group(2)

                    stats            = parse_stats_and_matches(stats_matches_str)
                    stats['actions'] = parse_actions(actions_str)

                    flows.append(stats)

            results.append({
                'name': "{0}".format(switch),
                'xid': xid,
                'flows': flows
            })

        return format_results( results )



    @validate_params(
        method_name = 'links',
        method_description = 'Retrieves all links in mininet',
    )
    @route('/links')
    def links():
        links = []
        for link in net.links:
            links.append({
                'name': "{0}".format(link),
                'status': link.status()
            })
        return { 'results': links }
    
    @validate_params(
        method_name = 'switches',
        method_description = 'Retrieves all switches in mininet',
    )
    @route('/switches')
    def switches():
        switches = []
        for switch in net.switches:
            # get our interfaces
            intfs = []
            for port in switch.intfs:
                intf = switch.intfs[port]
                intfs.append({
                    'name': intf.name,
                    'port': port
                })


            switches.append({
                'name': "{0}".format(switch),
                'dpid': switch.dpid,
                #'interfaces': switch.intfNames(),
                'interfaces': intfs,
                'controller_connection': switch.connected(),
                'ip': switch.IP(),
                'mac': switch.MAC(),
                'server': switch.cmd( 'hostname' ).strip()
            })
        return format_results( switches )
    
    @validate_params(
        method_name = 'hosts',
        method_description = 'Retrieves all hosts in mininet',
    )
    @route('/hosts')
    def hosts():
        hosts = []
        for host in net.hosts:
            # try to get the ip
            try:
                ip = host.IP()
            except:
                ip = None
            # try to get the mac addr
            try:
                mac = host.MAC()
            except:
                mac = None

            hosts.append({
                'name': "{0}".format(host),
                'interfaces': host.intfNames(),
                'ip': ip,
                'mac': mac,
                'server': host.cmd( 'hostname' ).strip()
            })
        return format_results( hosts )

    
    @route('/add_host')
    @validate_params(
        method_name = 'add_host',
        method_description = 'Adds a host to mininet',
        name = { 
            'required': True,
            'checks': [
                node_exists(success=False)
            ]
        },
        ip   = {},
        mask = {} 
    )
    def add_host(params):

        # pull out params
        name = params.get('name')
        ip   = params.get('ip')
        mask = params.get('mask')

        # format our ip
        cidr_ip = None
        if(( ip is not None) and (mask is not None)):
            cidr_ip = ip+"/"+mask

        # round robin our cluster servers
        server = get_next_server()
        if(server == 'localhost'):
            host = net.addHost(name, ip=cidr_ip)
        else:
            host = net.addHost(name, ip=cidr_ip, server=server)
        
        return format_results( [{'name': "{0}".format(host)}] )

    @route('/add_switch')
    @validate_params(
        method_name = 'add_switch',
        method_description = 'Adds a switch to mininet',
        name={ 'required': True, 'checks': [node_exists(success=False)] },
        dpid={ 'type': 'string' }
    )
    def add_switch(params):
        # pull out params
        name = params.get('name')
        dpid = params.get('dpid') 

        # round robin our cluster servers
        server = get_next_server()
        if(server == 'localhost'):
            switch = net.addSwitch(name, dpid=dpid)
        else:
            switch = net.addSwitch(name, dpid=dpid, server=server)

        if(is_running):
            switch.start(net.controllers)

        return format_results( [{'name': "{0}".format(switch)}] )

    @route('/add_switch_intf')
    @validate_params(
        method_name = 'add_switch_intf',
        method_description = 'Adds an interface to a switch in mininet',
        switch = {
            'required': True,
            'checks': [
                node_exists()
            ]
        },
        intf = { 'required': True },
        port = { 'required': True, 'type': 'integer' }
    )
    def add_switch_intf(params):
        # pull out params        
        switch_name = params.get('switch')
        intf_name   = params.get('intf')
        port        = params.get('port')

        switch = net.get(switch_name)
        intf   = Intf(intf_name, node=switch, port=port)
        
        return format_results( [{'name': "{0}".format(intf)}] )

    @route('/add_controller')
    @validate_params(
        method_name = 'add_controller',
        method_description = 'Adds a remote controller to mininet',
        name = { 'required': True },
        ip   = { 'required': True },
        port = { 'required': True, 'type': 'integer' }
    )
    def add_controller(params):
        # pull out params        
        name = params.get('name')
        ip = params.get('ip')
        port = params.get('port')

        # attach controller
        c0 = RemoteController( name=name, ip=ip, port=port )
        net.addController(c0)
        
        return format_results( [{'name': "{0}".format(c0)}] )

    @route('/add_link')
    @validate_params(
        method_name = 'add_link',
        method_description = 'Adds a link between two nodes in mininet',
        name   = {},
        node_a = { 'required': True, 'checks': [ node_exists(success=True) ] },
        node_z = { 'required': True, 'checks': [ node_exists(success=True) ] },
        port_a = { 'type': 'integer' },
        port_z = { 'type': 'integer' },
        intf_a = {},
        intf_z = {}
    )
    def add_link(params):
        # pull out params
        name   = params.get('name')
        node_a = params.get('node_a')
        node_z = params.get('node_z')
        port_a = params.get('port_a')
        port_z = params.get('port_z')
        intf_a = params.get('intf_a')
        intf_z = params.get('intf_z')

        link = net.addLink(
            node_a, 
            node_z,
            port1=port_a,
            port2=port_z,
            intfName1=intf_a,
            intfName2=intf_z,
            name=name
        )

        if(is_running):
            for controller in net.controllers:
                controller.stop()
                controller.start()
            for node in nodes:
                node.stop()
                node.start( net.controllers )

        return format_results( [{'name': "{0}".format(link)}] )

    @route('/delete_link')
    @validate_params(
        method_name = 'delete_link',
        method_description = 'Deletes a link in mininet',
        link   = { 'required': True },
        status = {}
    )
    def delete_link(params):
        # pull out params
        link_name = params.get('link')

        for link in net.links:
            if("{0}".format(link) == link_name):
                link.stop()
                link.delete()
                net.links.remove(link)
                return format_results ([{'success': 1}])

        return format_results(None, "Unable to find link {0}".format(link_name))
    
    @route('/update_link')
    @validate_params(
        method_name = 'update_link',
        method_description = 'Updates a link in mininet',
        link = { 'required': True, 'checks': [ link_exists() ] },
        status = { 'pattern': '^(1|0)$', 'type': 'integer' }
    )
    def update_link(params):
        link   = params.get('link')
        status = params.get('status')
        link = net.getLink(name=link);

        if(status is not None):
            if(status == 1):
                # make link up by up'ing it's first interface
                out, err, code = link.node1.pexec('ifconfig {0} up'.format(link.intf1.br_name))
                if(code):
                     return format_results(out, err)
                return format_results([{
                    'status': link.status(),
                }])

            else:
                # make link up by up'ing it's first interface
                out, err, code = link.node1.pexec('ifconfig {0} down'.format(link.intf1.br_name))
                if(code):
                    return format_results(out, err)
                return format_results([{
                    'status': link.status()
                }])

        return format_results(None, 'Must pass in a parameter to update')

    @route('/update_switch')
    @validate_params(
        method_name = 'update_switch',
        method_description = 'Adds a node in mininet',
        switch = { 'required': True, 'checks': [ node_exists(success=True) ] },
        status = { 'pattern': '^(1|0)$', 'type': 'integer' }
    )
    def update_switch(params):
        switch = params.get('switch')
        status = params.get('status')
        sw = net.get(switch)
        print "Status: %d\n" % status
        if(status == 1):
            print "Starting switch %s\n" % switch
            sw.start(net.controllers)
            return {'name': "{0}".format(sw),
                'dpid': sw.dpid,
                'controller_connection': sw.connected(),
                'ip': sw.IP(),
                'mac': sw.MAC(),
                'server': sw.cmd( 'hostname' ).strip()
        }
        else:
            print "Stopping switch %s\n" % switch
            sw.stop()
            return {'name': "{0}".format(sw),
                'dpid': sw.dpid,
                'controller_connection': False,
        }
            

    @route('/add_remote_link')
    @validate_params(
        method_name = 'add_link',
        method_description = 'Adds a link between two nodes in mininet',
        name   = {},
        node = { 'required': True, 'checks': [ node_exists(success=True) ] },
        port = { 'type': 'integer' },
        intf = {},
        dest_addr = { 'required':True },
    )
    def add_remote_link(params):
        # pull out params
        name   = params.get('name')
        node = params.get('node')
        port = params.get('port')
        intf = params.get('intf')
        dest_addr = params.get('dest_addr')
        
        link = net.addCustomLink(
            node,
            port=port,
            intfName=intf,
            name=name,
            destAddr=dest_addr,
            localAddr=get_ip_address('eth0'),
        )

        if(is_running):
            for controller in net.controllers:
                controller.stop()
                controller.start()
            for node in nodes:
                node.stop()
                node.start( net.controllers )

        return format_results( [{'name': "{0}".format(link)}] )

    @route('/stop')
    @validate_params(
        method_name = 'stop',
        method_description = 'Stops mininet and reinitializes network',
    )
    def stop(params):
        global net
        global is_running
        # if mn is running stop and reinitialize, seems to crash
        # if you try starting it again without reinitializing need to dig a bit further
        if(is_running):
            ret = net.stop()
            is_running = False
            net  = Mininet(
                topo=None,
                build=False,
                switch=OVSSwitch,
                controller=RemoteController,
                link=Link,
                host=Host
            )
            return format_results( [{ "msg": "Successfully stopped mininet" }] )
        else:
            return format_results( [{ "msg": "Mininet was already stopped" }] )
    
    @route('/start')
    @validate_params(
        method_name = 'start',
        method_description = 'Starts mininet network',
    )
    def start(params):
        global is_running
        if(not is_running):
            net.start()
            is_running = True
            return format_results( [{ "msg": "Successfully started mininet" }] )
        else:
            return format_results( [{ "msg": "Mininet was already running" }] )
    
    @route('/status')
    @validate_params(
        method_name = 'status',
        method_description = 'Returns the status of the mininet network and counts of the network elements',
    )
    def status(params):
        return format_results( [{
            "is_running": is_running,
            "switch_count": len(net.switches),
            "host_count": len(net.hosts),
            "link_count": len(net.links)
        }] )
    
    @route('/reset')
    @validate_params(
        method_name = 'reset',
        method_description = 'Stops mininet and reinitializes network even if the network was not running',
    )
    def reset(params):
        global net
        global is_running

        net.stop()
        is_running = False
        
        # reinitialize mininet
        net = Mininet(
            topo=None,
            build=False,
            switch=OVSSwitch,
            controller=RemoteController,
            link=Link,
            host=Host
        )
        return format_results( [{ "msg": "Mininet was been reset" }] )

    @route('/')
    @route('/help')
    @validate_params(
        method_name = 'help',
        method_description = 'Returns information about what methods are available and their parameters if a method is specified',
        method = {}
    )
    def help(params):
        method = params.get('method')

        methods = None
        if(method is not None):
            try:
                methods = [method_list.get(method)]
                methods[0]['name'] = method
            except:
                return format_results( None, "Method, {0}, does not exists".format(method) )
        else:
            methods = method_list.keys()

        methods.sort()
        return format_results( methods )

    run(host="0.0.0.0", port=8080)

    if(is_running):
        net.stop()

main()
