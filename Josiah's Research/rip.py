#!/usr/bin/python3

# credit: http://intronetworks.cs.luc.edu/current/html/mininet.html

# simple implementation of RIPv2
# no split horizon, no triggered updates, no hold down
# In the language of RFC 2453, there are no request messages, only updates.
# We avoid using threads.
# ALL update messages are sent via multicast; there is no "neighbor discovery"

import socket
import os
import time
import select
import struct
import fcntl
import subprocess
#import netifaces

MADDR = '224.0.0.9'
MPORT = 520		# used as both source and destination port
UPDATE_INTERVAL = 10	# seconds; 5-10 is good when run from an xterm
SOCK_SIZE = 2048
READ_TIMEOUT = 1.0
#IP_MULTICAST_LOOP = 34
#IP_MULTICAST_IF   = 32
RIP_ENTRY_SIZE    = 20
RIP_HEADER_SIZE   = 4

# RIP flags
UPDATECMD  = 2
TEXTMSGCMD = 3		# for the send_update2() demo option, below
VER_RIP2  = 2

# do we actually make calls to change the system forwarding tables?
MODTABLES = True

"""
header word: command(1), version(1), zero(2). As bytes: [2,2,0,0]
rip_entry: AF(2), route_tag(2), IP_addr(4), mask(4), next_hop(4), metric(4)
"""


# arriving RIPv2 messages are parsed into class RipEntry objects

class RipEntry:
    def __init__(self, af, tag, ipaddr, mask, nexthop, metric):
        self.af_      = af		# must be socket.AF_INET (=2)
        self.tag_     = tag		# must be zero
        self.ipaddr_  = ipaddr		# in 32-bit numeric format
        self.mask_    = mask		# in 32-bit numeric format
        self.nexthop_ = nexthop		# zero means send to neighbor that advertised route
        self.metric_  = metric
    def ipaddr(self): return self.ipaddr_
    def mask(self):   return self.mask_
    def metric(self): return self.metric_
    def nexthop(self): return self.nexthop_
    def af(self):     return self.af_
    def tag(self):     return self.tag_

# TableKey is the key to the shadow routing table RTable
class TableKey:
    def __init__(self, ipaddrn, netmaskn):    # ipaddrn and netmaskn as 32-bit integers
        self.ipaddrn_  = ipaddrn
        self.netmaskn_ = netmaskn
    def ipaddr(self): return self.ipaddrn_
    def netmask(self):   return self.netmaskn_
    def __hash__(self):
        return hash(self.ipaddrn_) ^ hash(self.netmaskn_)
    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.ipaddrn_ == other.ipaddrn_ and self.netmaskn_ == other.netmaskn_
        else:
            return False

class TableValue:
    def __init__(self, interface, nexthop, metric):
        self.interface_ = interface	# never used here; might be needed for poison reverse
        self.nexthop_   = nexthop	# in dotted-quad string format
        				# zero means send to neighbor that advertised route
        self.metric_    = metric
    def interface(self): return self.interface_
    def nexthop(self):   return self.nexthop_
    def metric(self):    return self.metric_

# RTable is our current dictionary of <TableKey,TableValue> pairs, a shadow copy of the real forwarding table

RTable = {}


def main():
    IFADDRS = getifaddrdict()
    myInterfaces = list(IFADDRS.keys())
    myIPaddrs = list(map(lambda x: x[0], IFADDRS.values()))
    print('interfaces:', list(IFADDRS.keys()))
    print('ipaddrs:', list(map(lambda x: x[0], IFADDRS.values())))

    socks = createMcastSockets(IFADDRS)

    starttime = time.time()
    next_update_time = starttime
    while True:
        if time.time() >= next_update_time:
            next_update_time += UPDATE_INTERVAL
            send_update(socks)
        ready_sockets,_,_ = select.select(socks, [], [], READ_TIMEOUT)
        if ready_sockets == []: continue		# READ_TIMEOUT occurred
        for s in ready_sockets:		# normally just one socket
            try:
                msg,src = s.recvfrom(SOCK_SIZE)
            except socket.timeout:
                msg = None
            if msg == None: continue
            (saddr,sport) = src			# saddr is in dotted-quad-string format

            if saddr in myIPaddrs:
                print('received update message from self, via IP address {}'.format(saddr))
                continue

            if not validate_header(msg, saddr): continue
            riplist = parse_msg(msg, saddr)
            ### print('RIPmsg list of length {} received from {}'.format(len(riplist), saddr))
            update_tables(riplist, saddr)

# The following returns a dictionary mapping interface names to their IPv4 address (or first such address, if there are more than one).

def getifaddrdict():
    myInterfaces = os.listdir('/sys/class/net/')	# now use SIOCGIFADDR, SIOCGIFNETMASK
    myInterfaces.remove('lo')		# we don't want to multicast to ourself!
    ifaddrs = {}
    for intf in myInterfaces:
        ifaddrs[intf] = get_ip_info(intf)
    return ifaddrs

# get first IP address and netmask of an interface, in dotted-quad format
def get_ip_info(intf):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    SIOCGIFADDR    = 0x8915	# from /usr/include/linux/sockios.h
    SIOCGIFNETMASK = 0x891b	
    intfpack = struct.pack('256s', bytes(intf, 'ascii'))
    # ifreq, below, is like struct ifreq in /usr/include/linux/if.h
    ifreq    = fcntl.ioctl(s.fileno(), SIOCGIFADDR, intfpack)
    ipaddrn  = ifreq[20:24]	# 20 is the offset of the IP addr in ifreq
    ipaddr   = socket.inet_ntoa(ipaddrn)
    netmaskn = fcntl.ioctl(s.fileno(), SIOCGIFNETMASK, intfpack)[20:24]
    netmask  = socket.inet_ntoa(netmaskn)
    return (ipaddr, netmask)

# create and configure a socket for each (non-loopback) interface
def createMcastSockets(ifaddrs):
    socks = []
    for intf in ifaddrs:
        (ipaddr, netmask)  = ifaddrs[intf]
        ipaddrn = aton(ipaddr)  	# convert to 32-bit numeric format
        netmaskn= aton(netmask)
        subnetn = ipaddrn & netmaskn
        RTable[TableKey(subnetn, netmaskn)] = TableValue(intf, None, 1)
        print ('interface: '+intf)
        print('ipaddr of {} is {}/{}'.format(intf, ipaddr, slash(netmaskn)))
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.settimeout(READ_TIMEOUT)
        # The following sets the IP header TTL value. 1 means Do Not Forward
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)	# prevents "address already in use" errors when we call sock.bind below
        # The next call makes the socket RECEIVE only on the specified interface
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BINDTODEVICE, bytes(intf, 'ascii'))
        # The following prevents transmitted packets from being delivered back to the sender
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, False)
        # The next call makes the socket TRANSMIT only on the specified interface
        # socket.inet_aton() returns a bytestring, not an integer
        # No apparent change if this is omitted, because of the subsequent call
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, socket.inet_aton(ipaddr))
        # next call is for joining a multicast group; it is essential for communication.
        try:
            addrpair = socket.inet_aton(MADDR)+ socket.inet_aton(ipaddr)
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, addrpair)
        except OSError as ose:
            print('IP_ADD_MEMBERSHIP failed: {}'.format(ose))
        sock.bind((MADDR, MPORT)) 	 # (MADDR,MPORT) is our multicast group
        socks.append(sock)
    return socks

# update_sender is the IP address in dotted-quad string form of the sender of this update
def update_tables(riplist, update_sender):
    global RTable
    for entry in riplist:
        if entry.af() != socket.AF_INET: continue
        if entry.tag()!= 0: continue
        if entry.nexthop()!= 0: continue
        ipaddrn = entry.ipaddr()	# n for numeric form
        netmaskn = entry.mask()
        ipaddr = ntoa(ipaddrn)
        netmask = ntoa(netmaskn)
        if ipaddrn != (ipaddrn & netmaskn):
            print ('warning: address {} inconsistent with mask {}'.format(ipaddr, netmask))
        cost = entry.metric()
        TK = TableKey(ipaddrn, netmaskn)
        if TK in RTable:	# we have an existing entry for this destination
            TVal = RTable[TK]
            currentcost = TVal.metric()
            currentnexthop = TVal.nexthop()
            newcost = entry.metric() + 1
            if (
                (newcost < currentcost)  # lower-cost route
                    or
                (newcost > currentcost and currentnexthop == update_sender)  # next_hop increase
            ):
                interface = None
                RTable[TK] = TableValue(interface, update_sender, newcost)
                call_list = ['/sbin/route', 'change', '-net', ipaddr, 'netmask', netmask, 'gw', update_sender]
                print ('updating route to {}/{}'.format(ipaddr, slash(aton(netmask))))
                if MODTABLES: subprocess.call(call_list)
        else:		# this is a new destination
           interface = None
           cost = entry.metric() + 1
           RTable[TK] = TableValue(interface, update_sender, cost)
           call_list = ['/sbin/route', 'add', '-net', ipaddr, 'netmask', netmask, 'gw', update_sender]
           print ('adding route to new destination {}/{}'.format(ipaddr, slash(aton(netmask))))
           if MODTABLES: subprocess.call(call_list)


def send_update(socks):
    buf = struct.pack('>BBh', UPDATECMD, VER_RIP2, 0)   # two unsigned bytes and a halfword, in network byte order
    for dest in RTable:
        ipaddrn = dest.ipaddr()
        netmaskn = dest.netmask()
        cost = RTable[dest].metric()
        buf += struct.pack('>HHIIII', socket.AF_INET,0, ipaddrn,netmaskn,0,cost)
    for s in socks:
        s.sendto(buf, (MADDR, MPORT))

# The following alternative send_update is used to send demonstration text messages instead of RIP updates
def send_update2(socks):
    buf = struct.pack('>BBh', TEXTMSGCMD, VER_RIP2, 0)   # two unsigned bytes and a halfword, in network byte order
    buf += 'here is the multicast message'.encode('utf-8')
    print('sending multicast message')
    for s in socks:
        s.sendto(buf, (MADDR, MPORT))


def parse_msg(msg, src):
    offset = RIP_HEADER_SIZE
    riplist = []
    while len(msg)-offset >= RIP_ENTRY_SIZE:
        (af, tag, ipaddr, mask, nexthop, metric) = struct.unpack_from('>HHIIII', msg, offset)
        offset += RIP_ENTRY_SIZE
        if af != socket.AF_INET:
            continue
        riplist.append(RipEntry(af, tag, ipaddr, mask, nexthop, metric))
    return riplist

def validate_header(msg, src):
    (command, version, zero) = struct.unpack_from('>BBh', msg, 0)
    if command==UPDATECMD and version == VER_RIP2 and zero==0:
        return True
    elif command == TEXTMSGCMD:
        print('text message from {}: {}'.format(src, msg[4:].decode('utf-8')))
        return False
    else:
        print('received unknown RIPv2 message')
        return False


# def aton(ip): return int(socket.inet_aton(ip).encode('hex'),16)

# converts a netmask in 32-bit format to a slash number, eg 0xfffff000 -> /20
def slash(maskn):
    i = 0
    while maskn & 0xffffffff != 0:
       maskn = maskn << 1
       i += 1
    return i

def aton(ip):
    return struct.unpack(">I", socket.inet_aton(ip))[0]

def ntoa(ip):
    return socket.inet_ntoa(struct.pack(">I", ip))


main()
