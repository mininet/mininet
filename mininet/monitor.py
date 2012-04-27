from time import sleep, time
from subprocess import Popen, PIPE
from multiprocessing import Process
import re
import os

from mininet.log import info, error, debug, output
from mininet.util import quietRun

class Monitor(object):

    def __init__(self, output_dir='/tmp'):
        self.monitors = []
        self.output_dir = output_dir

        # Create output directory if it doesn't exist already
        debug('Monitoring output dir: %s' % self.output_dir)
        if not os.path.isdir(self.output_dir):
            os.makedirs(self.output_dir)

        # Add general process monitors
        # Bandwidth monitor
        self.monitors.append(Process(target=self.monitor_devs_ng,
            args=('%s/bwm.txt' % self.output_dir, 1.0)))

        # CPU monitor
        self.monitors.append(Process(target=self.monitor_cpu,
            args=('%s/cpu.txt' % self.output_dir, )))

    def start(self):
        '''Start all the system monitors'''
        # Start the monitors
        for m in self.monitors:
            m.start()

    def stop(self):
        '''Terminate all the system monitors'''
        # Stop the monitors
        for m in self.monitors:
            m.terminate()
        self.monitors = []
        os.system("killall -9 bwm-ng top")

    def monitor_qlen(self, iface, interval_sec = 0.01, fname='%s/qlen.txt' % '.'):
        pat_queued = re.compile(r'backlog\s[^\s]+\s([\d]+)p')
        cmd = "tc -s qdisc show dev %s" % (iface)
        ret = []
        open(fname, 'w').write('')
        while 1:
            p = Popen(cmd, shell=True, stdout=PIPE)
            output = p.stdout.read()
            # Not quite right, but will do for now
            matches = pat_queued.findall(output)
            if matches and len(matches) > 1:
                ret.append(matches[1])
                t = "%f" % time()
                open(fname, 'a').write(t + ',' + matches[1] + '\n')
            sleep(interval_sec)
        return

    def monitor_count(self, ipt_args="--src 10.0.0.0/8", interval_sec=0.01, fname='%s/bytes_sent.txt' % '.', chain="OUTPUT"):
        cmd = "iptables -I %(chain)s 1 %(filter)s -j RETURN" % {
            "filter": ipt_args,
            "chain": chain,
            }
        # We always erase the first rule; will fix this later
        Popen("iptables -D %s 1" % chain, shell=True).wait()
        # Add our rule
        Popen(cmd, shell=True).wait()
        open(fname, 'w').write('')
        cmd = "iptables -vnL %s 1 -Z" % (chain)
        while 1:
            p = Popen(cmd, shell=True, stdout=PIPE)
            output = p.stdout.read().strip()
            values = output.split(' ')
            if len(values) > 2:
                t = "%f" % time()
                pkts, bytes = values[0], values[1]
                open(fname, 'a').write(','.join([t, pkts, bytes]) + '\n')
            sleep(interval_sec)
        return

    def monitor_devs(self, dev_pattern='^sw', fname="%s/bytes_sent.txt" % '.', interval_sec=0.01):
        """Aggregates (sums) all txed bytes and rate (in Mbps) from devices whose name
        matches @dev_pattern and writes to @fname"""
        pat = re.compile(dev_pattern)
        spaces = re.compile('\s+')
        open(fname, 'w').write('')
        prev_tx = {}
        while 1:
            lines = open('/proc/net/dev').read().split('\n')
            t = str(time())
            total = 0
            for line in lines:
                line = spaces.split(line.strip())
                iface = line[0]
                if pat.match(iface) and len(line) > 9:
                    tx_bytes = int(line[9])
                    total += tx_bytes - prev_tx.get(iface, tx_bytes)
                    prev_tx[iface] = tx_bytes
            open(fname, 'a').write(','.join([t, str(total * 8 / interval_sec / 1e6), str(total)]) + "\n")
            sleep(interval_sec)
        return

    def monitor_devs_ng(self, fname="%s/txrate.txt" % '.', interval_sec=0.01):
        """Uses bwm-ng tool to collect iface tx rate stats.  Very reliable."""
        cmd = "sleep 1; bwm-ng -t %s -o csv -u bits -T rate -C ',' > %s" % (interval_sec * 1000, fname)
        Popen(cmd, shell=True).wait()

    def monitor_cpu(self, fname="%s/cpu.txt" % '.'):
        cmd = "(top -b -p 1 -d 1 | grep --line-buffered \"^Cpu\") > %s" % fname
        Popen(cmd, shell=True).wait()

    def monitor_cpuacct(self, hosts, fname="%s/cpuacct.txt" % '.', interval_sec=1.0):
        prereqs = ['cgget']
        for p in prereqs:
            if not quietRun('which ' + p):
                error('Could not find %s... not monitoring cpuacct' % p)
                return
        hnames = ' '.join([h.name for h in hosts])
        cpuacct_cmd = 'cgget -g cpuacct %s >> %s' % (hnames, fname)
        prev_time = time()
        while 1:
            sleep(interval_sec - (time() - prev_time))
            prev_time = time()
            cpu_usage = Popen(cpuacct_cmd, shell=True).wait()
        return

