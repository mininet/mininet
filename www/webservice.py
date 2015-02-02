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
from mininet.log import setLogLevel
from mininet.link import Intf, Link
#from subprocess import check_call
import subprocess 
import urllib

# import bottle framework
from bottle import route, run, template, request
import os
try:
    user_paths = os.environ['PYTHONPATH'].split(os.pathsep)
except KeyError:
    user_paths = []
print "user_paths: {0}".format(user_paths)
setLogLevel( 'info' )
print sys.path

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
        return wrapper

    # special decorator that takes in kwargs where the key is the parameter
    # and the value is an object representing the validation it should do to the 
    # parameter
    def validate_params( **kwargs ):
        validators = kwargs
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
                                return format_results( None, "Parameter, {0}, must match pattern".format(param, pattern) )
                        # if the param has any special check perform them now
                        for check in checks:
                            print "calling check"
                            err, msg = check( value )
                            print "got err {0} and msg {1}".format(err, msg)
                            if(err):
                                return format_results( None, msg )

                    # if we've gotten here the param is good so add it to our validated params
                    validated_args[param] = value


                return func(validated_args)
            return wrapper
        return validate_params_decorator


    # note this method is dangerous since it allows you to run any command, and the commands are run
    # as root, would be fine in are setup given the firewalls but we should make more specific commands
#    @route('/cmd/<node>/<cmd>')
#    def node_cmd( node, cmd='hostname' ):
#        try:
#            node_obj = net.get( node )
#        except KeyError:
#            err = "Node, {0}, does not currently exists in the mininet topology".format(node) 
#            return format_results( None, err, 1 )
#        except: 
#            e = sys.exc_info()[0]
#            err = "Encountered an error while trying to retrieve {0} instance: {1}".format(node, str(e))
#            return format_results( None, err, 1 )
#
#        out, err, code = node_obj.pexec( cmd )
#        return format_results( out, err, code )


    @route('/flows')
    @validate_params(
        node = { 'checks': [ node_exists() ] }
    )
    def flows( params ):
        if(not is_running):
            return format_results( None, "Can not retrieve flow stats when mn is not running" )

        # pull out params
        node_name = params.get('node')

        nodes = []
        if(node_name):
            nodes.append(net.get(node_name))
        else:
            nodes = net.switches 

        # this will convert the string blob returned by dump-flows into an object
        def parse_stats_and_matches(str):
            stats = { 'matches': {} }
            for kvp_str in str.split(','):
                # get rid of leading and trailing whitespace
                kvp_str = kvp_str.strip()
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

        # now loop through our nodes getting their stats
        results = []
        for node in nodes:
            flow_txt = node.dpctl('dump-flows')

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
            if(flows_blob != ' '):
                # split on new lines to get a flow
                for flow_blob in flows_blob.split('\r\n'):
                    # use regex to split the stats, matches, and actions
                    capture = re.search('(.*) actions=(.*)', flow_blob)
                    stats_matches_str = capture.group(1)
                    actions_str       = capture.group(2)

                    stats            = parse_stats_and_matches(stats_matches_str)
                    stats['actions'] = actions_str.split(',')

                    flows.append(stats)

            results.append({
                'name': "{0}".format(node),
                'xid': xid,
                'flows': flows
            })

        return format_results( results )

    @route('/links')
    def links():
        links = []
        for link in net.links:
            links.append({
                'name': "{0}".format(link),
                'status': link.status()
            })
        return { 'results': links }
    
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

        print "ip: {0}".format(ip)
        print "mask: {0}".format(mask)

        # format our ip
        cidr_ip = None
        if(( ip is not None) and (mask is not None)):
            cidr_ip = ip+"/"+mask

        print "cidr: {0}".format(cidr_ip)

        # round robin our cluster servers
        server = get_next_server()
        if(server == 'localhost'):
            host = net.addHost(name, ip=cidr_ip)
        else:
            host = net.addHost(name, ip=cidr_ip, server=server)
        
        return format_results( [{'name': "{0}".format(host)}] )

    @route('/add_switch')
    @validate_params(
        name={ 'required': True },
        dpid={}
    )
    def add_switch(params):
        # pull out params
        name = params.get('name')
        dpid = params.get('dpid') 

        # round robin our cluster servers
        server = get_next_server()
        if(server == 'localhost'):
            switch = net.addSwitch(name, dpid=str(dpid))
        else:
            switch = net.addSwitch(name, dpid=str(dpid), server=server)

        if(is_running):
            switch.start(net.controllers)

        return format_results( [{'name': "{0}".format(switch)}] )

    @route('/add_switch_intf')
    @validate_params(
        switch = {
            'required': True,
            'checks': [
                node_exists()
            ]
        },
        intf = { 'required': True },
        port = { 'required': True }
    )
    def add_switch_intf(params):
        # pull out params        
        switch_name = params.get('switch')
        intf_name   = params.get('intf')
        port        = params.get('port')

        switch = net.get(switch_name)
        intf   = Intf(switch_name+'-'+intf_name, node=switch, port=int(port))
        #intf   = Intf(switch_name+'-'+intf_name, node=switch )
        
        return format_results( [{'name': "{0}".format(intf)}] )

    @route('/add_controller')
    @validate_params(
        name = { 'required': True },
        ip   = { 'required': True },
        port = { 'required': True }
    )
    def add_controller(params):
        # pull out params        
        name = params.get('name')
        ip = params.get('ip')
        port = params.get('port')

        # attach controller
        c0 = RemoteController( name=name, ip=ip, port=int(port) )
        net.addController(c0)
        
        return format_results( [{'name': "{0}".format(c0)}] )

    @route('/add_link')
    @validate_params(
        node_a = { 'required': True, 'checks': [ node_exists(success=True) ] },
        node_z = { 'required': True, 'checks': [ node_exists(success=True) ] },
        port_a = {},
        port_z = {},
        intf_a = {},
        intf_z = {}
    )
    def add_link(params):
        # pull out params
        node_a = params.get('node_a');
        node_z = params.get('node_z');
        port_a = params.get('port_a');
        port_z = params.get('port_z');
        intf_a = params.get('intf_a');
        intf_z = params.get('intf_z');

        # get node instances 
        #node_a = net.get(node_a)
        #node_z = net.get(node_z)
        #print "intfs {0}: ".format(node_a.intfs)

        if(port_a is not None):
            port_a = int(port_a)

        if(port_z is not None):
            port_z = int(port_z)
                
        link = net.addLink(
            node_a, 
            node_z,
            port1=port_a,
            port2=port_z,
            intfName1=intf_a,
            intfName2=intf_z
        )

        if(is_running):
            for controller in net.controllers:
                controller.stop()
                controller.start()
            for node in nodes:
                node.stop()
                node.start( net.controllers )
#                for intf in node.intfList():
#                    print "INterface: {0}".format(intf.status())
#                    print "{0}".format(intf.isUp())
#                    print "{0}".format(intf.ifconfig())
#                    if(intf.status() != "up"):
#                        node.attach(intf)

        return format_results( [{'name': "{0}".format(link)}] )

    @route('/delete_link/<link_name>')
    @validate_params(
        link = {} 
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

    @route('/stop')
    def stop():
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
                switch=RemoteOVSSwitch,
                controller=RemoteController,
                link=RemoteLink,
                host=RemoteHost
            )
            return format_results( [{ "msg": "Successfully stopped mininet" }] )
        else:
            return format_results( [{ "msg": "Mininet was already stopped" }] )
    
    @route('/start')
    def start():
        global is_running
        if(not is_running):
            net.start()
            is_running = True
            return format_results( [{ "msg": "Successfully started mininet" }] )
        else:
            return format_results( [{ "msg": "Mininet was already running" }] )
    
    @route('/status')
    def status():
        return format_results( [{
            "is_running": is_running,
            "switch_count": len(net.switches),
            "host_count": len(net.hosts),
            "link_count": len(net.links)
        }] )
    
    @route('/reset')
    def reset():
        global net
        global is_running

        net.stop()
        is_running = False
        
        # reinitialize mininet
        net  = Mininet(
            topo=None,
            build=False,
            switch=RemoteOVSSwitch,
            controller=RemoteController,
            link=RemoteLink,
            host=RemoteHost
        )
        return format_results( [{ "msg": "Mininet was been reset" }] )


    run(host=get_ip_address('eth0'), port=8080)

    if(is_running):
        net.stop()

main()
