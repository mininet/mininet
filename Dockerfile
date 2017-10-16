
FROM ubuntu:16.04

MAINTAINER ringtail <zhongwei.lzw@alibaba-inc.com>

USER root
WORKDIR /root

ADD ./sources.list /etc/apt/

RUN apt-get update -y \
    && apt-get upgrade -y   \
    && apt-get dist-upgrade -y \
    && apt-get install -y --no-install-recommends \
        apt-utils \
        build-essential \
        curl \
        iproute2 \
        iputils-ping \
        openvswitch-testcontroller \
        net-tools \
        tcpdump \
        vim \
        x11-xserver-utils \
        xterm   \
        git     \
        sudo 

RUN git clone git://github.com/mininet/mininet \
    && cd mininet \
    && git checkout -b 2.2.2 \
    && cd .. \
    && mininet/util/install.sh

RUN rm -rf /var/lib/apt/lists/*

ENV TERM xterm-color
