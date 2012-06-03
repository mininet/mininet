#!/bin/sh
echo `pwd`
sed -i -s "s/Architecture: amd64/Architecture: i386/" DEBIAN/control

