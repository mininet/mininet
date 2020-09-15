#!/bin/bash

service openvswitch-switch start
ovs-vsctl set-manager ptcp:6640

function clean_exit {
  service openvswitch-switch stop
  echo "*** Exiting Container..."
  exit 0
}

sudo mn -c

if [ -z "$FILE_PATH" ]
then
  # Run using mn if no file path given
  sudo mn $MN_FLAGS
else
  # Use python api if a file path is given
  if [ ! -f "$FILE_PATH" ]
  then
    echo "*** Error: given file does not exist in container's filesystem"
    clean_exit
  fi
  sudo python3 $FILE_PATH
fi

clean_exit
