#!/usr/bin/env python
'''Setuptools params'''

from setuptools import setup, find_packages

setup(
    name='mininet',
    version='0.0.0',
    description='The OpenFlow-based data center network',
    author='Bob Lantz',
    author_email='rlantz@cs.stanford.edu',
    packages=find_packages(exclude='test'),
    long_description="""\
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
      license='GPL',
      install_requires=[
        'setuptools'
      ])
