#!/bin/bash

service openvswitch-switch start
ovs-vsctl set-manager ptcp:6640

sudo mn -c
sudo mn $MN_FLAGS

service openvswitch-switch stop
