#!/usr/bin/env python

"Setuptools params"

from setuptools import setup, find_packages
from os.path import join

# Get version number from source tree
import sys
sys.path.append( '.' )
from mininet.net import VERSION

scripts = [ join( 'bin', filename ) for filename in [ 'mn' ] ]

modname = distname = 'mininet'

setup(
    name=distname,
    version=VERSION,
    description='Process-based OpenFlow emulator',
    author='Bob Lantz',
    author_email='rlantz@cs.stanford.edu',
    packages=find_packages(exclude='test'),
    long_description="""
        Mininet is a network emulator which uses lightweight
        virtualization to create virtual networks for rapid
        prototyping of Software-Defined Network (SDN) designs
        using OpenFlow. http://openflow.org/mininet
        """,
    classifiers=[
          "License :: OSI Approved :: BSD License",
          "Programming Language :: Python",
          "Development Status :: 2 - Pre-Alpha",
          "Intended Audience :: Developers",
          "Topic :: Internet",
    ],
    keywords='networking emulator protocol Internet OpenFlow SDN',
    license='BSD',
    install_requires=[
        'setuptools',
        'networkx'
    ],
    scripts=scripts,
)
