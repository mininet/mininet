#!/usr/bin/env python

"Setuptools params"

from setuptools import setup, find_packages
from os.path import join

scripts = [ join( 'bin', filename ) for filename in [ 
    'mn', 'mnexec' ] ]

modname = distname = 'mininet'

setup(
    name=distname,
    version='0.0.0',
    description='Process-based OpenFlow emulator',
    author='Bob Lantz',
    author_email='rlantz@cs.stanford.edu',
    packages=find_packages(exclude='test'),
    long_description="""
Insert longer description here.
      """,
    classifiers=[
          "License :: OSI Approved :: GNU General Public License (GPL)",
          "Programming Language :: Python",
          "Development Status :: 4 - Beta",
          "Intended Audience :: Developers",
          "Topic :: Internet",
    ],
    keywords='networking protocol Internet OpenFlow',
    license='unspecified',
    install_requires=[
        'setuptools',
        'networkx'
    ],
    scripts=scripts,
)
