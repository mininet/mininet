#!/usr/bin/env python

"Setuptools params"

import os, setuptools
import distutils.command.build_scripts
import distutils.command.clean
import distutils.ccompiler

modname = distname = 'mininet'

class build_scripts(distutils.command.build_scripts.build_scripts):
    def run(self):
        distutils.ccompiler.new_compiler().link_executable(["mnexec.c"], "bin/mnexec")
        distutils.command.build_scripts.build_scripts.run(self)

class clean(distutils.command.clean.clean):
    def run(self):
        if os.path.exists("bin/mnexec"):
            os.unlink("bin/mnexec")
        distutils.command.clean.clean.run(self)

setuptools.setup(
    name=distname,
    version='0.0.0',
    description='Process-based OpenFlow emulator',
    author='Bob Lantz',
    author_email='rlantz@cs.stanford.edu',
    packages=setuptools.find_packages(exclude='test'),
    classifiers=[
          "License :: OSI Approved :: BSD",
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
    scripts=[
        'bin/mn',
        'bin/mnexec'
    ],
    cmdclass={"build_scripts": build_scripts,
              "clean": clean}
)
