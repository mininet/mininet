#!/usr/bin/python

"""
changingtclink.py: Example of changing TCLink limits

This example runs 3 iperf measurements and plots the resulting
throughputs:

The first run resets the bandwidth limit hard.
The second run resets the bandwidth smooth.
The third run resets the bandwidth limit to 'no limit'.

"""

import re
import os
from time import sleep

from mininet.net import Mininet
from mininet.link import TCIntf
from mininet.log import setLogLevel, info
from mininet.topo import Topo
from mininet.link import TCLink

import matplotlib.pyplot as plt

TARGET_BW = 500
INITIAL_BW = 200

class StaticTopo(Topo):
    "Simple topo with 2 hosts"
    def build(self):
        switch1 = self.addSwitch('s1')

        "iperf server host"
        host1 = self.addHost('h1')
        # this link is not the bottleneck
        self.addLink(host1, switch1, bw = 1000) 

        "iperf client host"
        host2 = self.addHost('h2')
        self.addLink(host2, switch1, bw = INITIAL_BW)

def plotIperf(traces):
    for trace in traces:
        bw_list = []
        for line in open(trace[0], 'r'):
            matchObj = re.match(r'(.*),(.*),(.*),(.*),(.*),(.*),(.*),(.*),(.*)', line, re.M)
            
            if matchObj:
                bw = float(matchObj.group(9)) / 1000.0 / 1000.0 # MBit / s
                bw_list.append(bw)
        plt.plot(bw_list, label=trace[1])

    plt.legend()
    plt.title("Throughput Comparison")
    plt.ylabel("Throughput [MBit / s]")
    plt.xlabel("Time")
    plt.show()

def measureChange(h1, h2, smooth_change, output_file_name, target_bw = TARGET_BW):
    info( "Starting iperf Measurement\n" )

    # stop old iperf server
    os.system('pkill -f \'iperf -s\'')
    
    h1.cmd('iperf -s -i 0.5 -y C > ' + output_file_name + ' &')
    h2.cmd('iperf -c ' + str(h1.IP()) + ' -t 10 -i 1 > /dev/null &')

    # wait 5 seconds before changing
    sleep(5)

    intf = h2.intf()
    info( "Setting BW Limit for Interface " + str(intf) + " to " + str(target_bw) + "\n" )
    intf.config(bw = target_bw, smooth_change = smooth_change)

    # wait a few seconds to finish
    sleep(10)
    
def limit():
    """Example of changing the TCLinklimits"""
    myTopo = StaticTopo()
        
    net = Mininet( topo=myTopo, link=TCLink )
    net.start()

    h1 = net.get('h1')
    h2 = net.get('h2')
    intf = h2.intf()

    traces = [] 

    filename = 'iperfServer_hard.log'
    measureChange(h1, h2, False, filename)
    traces.append((filename, 'Hard'))

    # reset bw to initial value
    intf.config(bw = INITIAL_BW)
    filename = 'iperfServer_smooth.log'
    measureChange(h1, h2, True, filename)
    traces.append((filename, 'Smooth'))

    # reset bw to initial value
    intf.config(bw = INITIAL_BW)

    filename = 'iperfServer_nolimit.log'
    measureChange(h1, h2, False, filename, target_bw = None)
    traces.append((filename, 'No limit'))

    net.stop()

    plotIperf(traces)

if __name__ == '__main__':
    setLogLevel( 'info' )
    limit()
