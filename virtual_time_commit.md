Introduction
============
This very primitive patch is the result of our paper [“VT-Mininet: Virtual-time-enabled Mininet for Scalable and Accurate Software-Define Network Emulation”], to appear on [ACM Sigcomm Symposium on SDN Research (SOSR) 2015](http://opennetsummit.org/conference/sosr/).

Mininet, as an examplary and ordinary network emulator, uses the system clock across all the containers, even if a container is not being scheduled to run. This leads to the issue of temporal fidelity, especially with high workloads.

Virtual time sheds the light on the issue of preserving temporal fidelity for large-scale emulation. The key insight is to trade time with system resources via precisely scaling the time of interactions between containers and physical devices by a factor of N (also called time dilation factor), hence, making an emulated network appear to be N times faster from the viewpoints of applications in the container than it actually is.

How to Use Virtual Time
=======================
When creating hosts, feed another parameter time dilation factor, "tdf". For example:
```
Host = custom( CPULimitedHost, sched = 'cfs', period_us = 100000, cpu = 0.8, tdf = 4 )
......# create Class for topo, switches etc
net = Mininet( topo = Topo, host = Host, switch = Switch, controller = Controller, waitConnected = True, link = Link )
```
TDF's default value is 1, e.g. no virtual time. So this patch should NOT cause compatible issues.


Test
====
I test this patch on my Dell XPS 8700 Desktop running on Ubuntu 14.04 LTS. We integrated virtual time with Mininet and conducted many experimental evaluations. Details can be found in our SOSR2015 paper. There is another similar paper on PADS2015 named [A Virtual Time System for Linux-container-based Emulation of Software-defined Networks](http://www.acm-sigsim-pads.org), though it focuses on simulation & emulation system and gives more comprehensive experimental results.
The integrated Mininet code, together with kernel patches, is also separately published at my [Github](https://github.com/littlepretty/VirtualTimeForMininet) website. In other words, to run Mininet with virtual time, one must first rebuild one's kernel. How to patch kernel is described in that repository's README file.

TODO List
=========
1. How to provide kernel patch? Option 1: provide patch file with respect to particualr kernel version. Option 2: provide already rebuilt virtual machine  image.
2. Summary some tests into one or two demos and place them under example diretory.
3. If the application inside container is at a very deep position of the process tree, setTDF will need to do cascading operations so that TDF of all processes in the tee, including host and all other applications inside the container, is properly changed. This is not implemented yet.
4. There are many other code regarding adaptive virtual time system. It is mentioned and discussed in both PADS and SOSR papers. However, it is still too immature.

