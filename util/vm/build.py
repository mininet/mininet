#!/usr/bin/python2

"""
build.py: build a Mininet VM

Basic idea:

    prepare
    -> create base install image if it's missing
        - download iso if it's missing
        - install from iso onto image

    build
    -> create cow disk for new VM, based on base image
    -> boot it in qemu/kvm with text /serial console
    -> install Mininet

    test
    -> sudo mn --test pingall
    -> make test

    release
    -> shut down VM
    -> shrink-wrap VM
    -> upload to storage

"""

import os
from os import stat, path
from stat import ST_MODE, ST_SIZE
from os.path import abspath
from sys import exit, stdout, argv, modules
import sys
import re
from glob import glob
from subprocess import check_output, call, Popen
from tempfile import mkdtemp, NamedTemporaryFile
from time import time, strftime, localtime
import argparse
from distutils.spawn import find_executable
import inspect
from traceback import print_exc


pexpect = None  # For code check - imported dynamically

# boot can be slooooow!!!! need to debug/optimize somehow
TIMEOUT = 600

# Some configuration options
# Possibly change this to use the parsed arguments instead!

LogToConsole = False        # VM output to console rather than log file
SaveQCOW2 = False           # Save QCOW2 image rather than deleting it
NoKVM = False               # Don't use kvm and use emulation instead
Branch = None               # Branch to update and check out before testing
Zip = False                 # Archive .ovf and .vmdk into a .zip file
Forward = []                # VM port forwarding options (-redir)
Chown = ''                  # Build directory owner

VMImageDir = os.environ[ 'HOME' ] + '/vm-images'

Prompt = '\$ '              # Shell prompt that pexpect will wait for


# URLs for Ubuntu .iso images

def serverURL( version, arch ):
    "Return .iso URL for Ubuntu version and arch"
    server = 'http://cdimage.ubuntu.com/ubuntu/releases/%s/release/'
    iso = 'ubuntu-%s-server-%s.iso'
    return (server + iso )  % ( version, version, arch )

def legacyURL( version, arch ):
    "Return .iso URL for Ubuntu version"
    server = ( 'http://cdimage.ubuntu.com/ubuntu-legacy-server/'
               'releases/%s/release/' )
    iso = 'ubuntu-%s-legacy-server-%s.iso'
    return (server + iso ) % ( version, version, arch )

isoURLs = {
    'precise64server':
    'http://mirrors.kernel.org/ubuntu-releases/12.04/'
    'ubuntu-12.04.5-server-amd64.iso',
    'trusty32server':
    'http://mirrors.kernel.org/ubuntu-releases/14.04/'
    'ubuntu-14.04.4-server-i386.iso',
    'trusty64server':
    'http://mirrors.kernel.org/ubuntu-releases/14.04/'
    'ubuntu-14.04.4-server-amd64.iso',
    'xenial32server':
    'http://mirrors.kernel.org/ubuntu-releases/16.04/'
    'ubuntu-16.04.6-server-i386.iso',
    'xenial64server':
    'http://mirrors.kernel.org/ubuntu-releases/16.04/'
    'ubuntu-16.04.7-server-amd64.iso',
    'bionic64server': serverURL( '18.04.5', 'amd64' ),
    'focal64server':  legacyURL( '20.04.1', 'amd64' ),
}


def OSVersion( flavor ):
    "Return full OS version string for build flavor"
    urlbase = path.basename( isoURLs.get( flavor, 'unknown' ) )
    return path.splitext( urlbase )[ 0 ]

def OVFOSNameID( flavor ):
    "Return OVF-specified ( OS Name, ID ) for flavor"
    version = OSVersion( flavor )
    arch = archFor( flavor )
    if 'ubuntu' in version:
        map = { 'i386': ( 'Ubuntu', 93 ),
                'x86_64': ( 'Ubuntu 64-bit', 94 ) }
    else:
        map = { 'i386': ( 'Linux', 36 ),
                'x86_64': ( 'Linux 64-bit', 101 ) }
    osname, osid = map[ arch ]
    return osname, osid

LogStartTime = time()
LogFile = None

def log( *args, **kwargs ):
    """Simple log function: log( message along with local and elapsed time
       cr: False/0 for no CR"""
    cr = kwargs.get( 'cr', True )
    elapsed = time() - LogStartTime
    clocktime = strftime( '%H:%M:%S', localtime() )
    msg = ' '.join( str( arg ) for arg in args )
    output = '%s [ %.3f ] %s' % ( clocktime, elapsed, msg )
    if cr:
        print( output )
    else:
        print( output, )
    # Optionally mirror to LogFile
    if LogFile:
        if cr:
            output += '\n'
        LogFile.write( output )
        LogFile.flush()


def run( cmd, **kwargs ):
    "Convenient interface to check_output"
    log( '+', cmd )
    cmd = cmd.split()
    arg0 = cmd[ 0 ]
    if not find_executable( arg0 ):
        raise Exception( 'Cannot find executable "%s";' % arg0 +
                         'you might try %s --depend' % argv[ 0 ] )
    return check_output( cmd, **kwargs )


def srun( cmd, **kwargs ):
    "Run + sudo"
    return run( 'sudo ' + cmd, **kwargs )


# BL: we should probably have a "checkDepend()" which
# checks to make sure all dependencies are satisfied!

def depend():
    "Install package dependencies"
    log( '* Installing package dependencies' )
    run( 'sudo apt-get -qy update' )
    run( 'sudo apt-get -qy install'
         ' kvmtool cloud-utils genisoimage qemu-kvm qemu-utils'
         ' e2fsprogs curl'
         ' python-setuptools mtools zip' )
    run( 'sudo easy_install pexpect' )


def popen( cmd ):
    "Convenient interface to popen"
    log( cmd )
    cmd = cmd.split()
    return Popen( cmd )


def remove( fname ):
    "Remove a file, ignoring errors"
    try:
        os.remove( fname )
    except OSError:
        pass


def findiso( flavor ):
    "Find iso, fetching it if it's not there already"
    url = isoURLs[ flavor ]
    name = path.basename( url )
    iso = path.join( VMImageDir, name )
    if not path.exists( iso ) or ( stat( iso )[ ST_MODE ] & 0o777 != 0o444 ):
        log( '* Retrieving', url )
        run( 'curl -L -C - -o %s %s' % ( iso, url ) )
        # Make sure the file header/type is something reasonable like
        # 'ISO' or 'x86 boot sector', and not random html or text
        result = run( 'file ' + iso )
        if 'ISO' not in result and 'boot' not in result:
            os.remove( iso )
            raise Exception( 'findiso: could not download iso from ' + url )
        # Write-protect iso, signaling it is complete
        log( '* Write-protecting iso', iso)
        os.chmod( iso, 0o444 )
    log( '* Using iso', iso )
    return iso


def attachNBD( cow, flags='' ):
    """Attempt to attach a COW disk image and return its nbd device
        flags: additional flags for qemu-nbd (e.g. -r for readonly)"""
    # qemu-nbd requires an absolute path
    cow = abspath( cow )
    log( '* Checking for unused /dev/nbdX device ' )
    for i in range ( 1, 63 ):
        entry = 'nbd%d' % i
        nbd = '/dev/' + entry
        # Check whether someone's already messing with that device
        if call( [ 'pgrep', '-f', entry ] ) == 0:
            continue
        srun( 'modprobe nbd max-part=64' )
        srun( 'qemu-nbd %s -c %s %s' % ( flags, nbd, cow ) )
        print()
        return nbd
    raise Exception( "Error: could not find unused /dev/nbdX device" )


def detachNBD( nbd ):
    "Detach an nbd device"
    srun( 'qemu-nbd -d ' + nbd )


def extractKernel( image, flavor, imageDir=VMImageDir ):
    "Extract kernel and initrd from base image"
    kernel = path.join( imageDir, flavor + '-vmlinuz' )
    initrd = path.join( imageDir, flavor + '-initrd' )
    log( '* Extracting kernel to', kernel )
    nbd = attachNBD( image, flags='-r' )
    try:
        print( srun( 'partx ' + nbd ) )
    except:
        log( 'Warning - partx failed with error' )
    # Guess that  kernel is in partition 1/boot/vmlinuz*generic
    # ...but look for other Linux partitions just in case
    part = nbd + 'p1'
    partitions = srun( 'fdisk -l ' + nbd )
    for line in partitions.split( '\n' ):
        line = line.strip()
        if line.endswith( 'Linux' ):
            part = line.split()[ 0 ]
            break
    partnum = int( part.split( 'p' )[ -1 ] )
    if path.exists( kernel ) and ( stat( image )[ ST_MODE ] & 0o777 ) == 0o444:
        # If kernel is there, then initrd should also be there
        detachNBD( nbd )
        return kernel, initrd, partnum
    mnt = mkdtemp()
    srun( 'mount -o ro,noload %s %s' % ( part, mnt  ) )
    kernsrc = glob( '%s/boot/vmlinuz*generic' % mnt )[ 0 ]
    initrdsrc = glob( '%s/boot/initrd*generic' % mnt )[ 0 ]
    srun( 'cp %s %s' % ( initrdsrc, initrd ) )
    srun( 'chmod 0444 ' + initrd )
    srun( 'cp %s %s' % ( kernsrc, kernel ) )
    srun( 'chmod 0444 ' + kernel )
    srun( 'umount ' + mnt )
    run( 'rmdir ' + mnt )
    detachNBD( nbd )
    return kernel, initrd, partnum


def findBaseImage( flavor, size='8G' ):
    "Return base VM image and kernel, creating them if needed"
    image = path.join( VMImageDir, flavor + '-base.qcow2' )
    if path.exists( image ):
        # Detect race condition with multiple builds
        perms = stat( image )[ ST_MODE ] & 0o777
        if perms != 0o444:
            raise Exception( 'Error - base image %s is writable.' % image +
                             ' Are multiple builds running? if not,'
                             ' remove %s and try again.' % image )
    else:
        # We create VMImageDir here since we are called first
        run( 'mkdir -p %s' % VMImageDir )
        iso = findiso( flavor )
        log( '* Creating image file', image )
        run( 'qemu-img create -f qcow2 %s %s' % ( image, size ) )
        installUbuntu( iso, image )
        # Write-protect image, also signaling it is complete
        log( '* Write-protecting image', image)
        os.chmod( image, 0o444 )
    kernel, initrd, partnum = extractKernel( image, flavor )
    log( '* Using base image', image, 'and kernel', kernel,
         'and partition #', partnum )
    return image, kernel, initrd, partnum


# Kickstart and Preseed files for Ubuntu/Debian installer
#
# Comments: this is really clunky and painful. If Ubuntu
# gets their act together and supports kickstart a bit better
# then we can get rid of preseed and even use this as a
# Fedora installer as well.
#
# Another annoying thing about Ubuntu is that it can't just
# install a normal system from the iso - it has to download
# junk from the internet, making this house of cards even
# more precarious.

KickstartText ="""
#Generated by Kickstart Configurator
#platform=x86

#System language
lang en_US
#Language modules to install
langsupport en_US
#System keyboard
keyboard us
#System mouse
mouse
#System timezone
timezone America/Los_Angeles
#Root password
rootpw --disabled
#Initial user
user mininet --fullname "mininet" --password "mininet"
#Use text mode install
text
#Install OS instead of upgrade
install
#Use CDROM installation media
cdrom
#System bootloader configuration
bootloader --location=mbr
#Clear the Master Boot Record
zerombr yes
#Partition clearing information
clearpart --all --initlabel
#Automatic partitioning
autopart
#System authorization information
auth  --useshadow  --enablemd5
#Firewall configuration
firewall --disabled
#Do not configure the X Window System
skipx
"""

# Tell the Ubuntu/Debian installer to stop asking stupid questions

PreseedText = ( """
"""
#d-i mirror/country string manual
#d-i mirror/http/hostname string mirrors.kernel.org
"""
d-i mirror/http/directory string /ubuntu
d-i mirror/http/proxy string
d-i partman/confirm_write_new_label boolean true
d-i partman/choose_partition select finish
d-i partman/confirm boolean true
d-i partman/confirm_nooverwrite boolean true
d-i user-setup/allow-password-weak boolean true
d-i finish-install/reboot_in_progress note
d-i debian-installer/exit/poweroff boolean true
""" )

def makeKickstartFloppy():
    "Create and return kickstart floppy, kickstart, preseed"
    kickstart = 'ks.cfg'
    with open( kickstart, 'w' ) as f:
        f.write( KickstartText )
    preseed = 'ks.preseed'
    with open( preseed, 'w' ) as f:
        f.write( PreseedText )
    # Create floppy and copy files to it
    floppy = 'ksfloppy.img'
    run( 'qemu-img create %s 1440k' % floppy )
    run( 'mkfs -t msdos ' + floppy )
    run( 'mcopy -i %s %s ::/' % ( floppy, kickstart ) )
    run( 'mcopy -i %s %s ::/' % ( floppy, preseed ) )
    return floppy, kickstart, preseed


def archFor( filepath ):
    "Guess architecture for file path"
    name = path.basename( filepath )
    if 'amd64' in name or 'x86_64' in name:
        arch = 'x86_64'
    # Beware of version 64 of a 32-bit OS
    elif 'i386' in name or '32' in name or 'x86' in name:
        arch = 'i386'
    elif '64' in name:
        arch = 'x86_64'
    else:
        log( "Error: can't discern CPU for name", name )
        exit( 1 )
    return arch


def installUbuntu( iso, image, logfilename='install.log', memory=1024 ):
    "Install Ubuntu from iso onto image"
    kvm = 'qemu-system-' + archFor( iso )
    floppy, kickstart, preseed = makeKickstartFloppy()
    # Mount iso so we can use its kernel
    mnt = mkdtemp()
    srun( 'mount %s %s' % ( iso, mnt ) )
    for kdir in 'install', 'casper':
        kernel = path.join( mnt, kdir, 'vmlinuz' )
        if not path.exists( kernel ):
            kernel = ''
        for initrd in 'initrd.gz', 'initrd':
            initrd = path.join( mnt, kdir, initrd )
            if path.exists( initrd ):
                break
            else:
                initrd = ''
        if kernel and initrd:
            break
    if not kernel or not initrd:
        raise Exception( 'unable to locate kernel and initrd in iso image' )
    if NoKVM:
        accel = 'tcg'
    else:
        accel = 'kvm'
        try:
            run( 'kvm-ok' )
        except:
            raise Exception( 'kvm-ok failed; try using --nokvm' )
    cmd = [ 'sudo', kvm,
           '-machine', 'accel=%s' % accel,
           '-nographic',
           '-netdev', 'user,id=mnbuild',
           '-device', 'virtio-net,netdev=mnbuild',
           '-m', str( memory ),
           '-k', 'en-us',
           '-fda', floppy,
           '-drive', 'file=%s,if=virtio' % image,
           '-cdrom', iso,
           '-kernel', kernel,
           '-initrd', initrd,
           '-append',
           ' ks=floppy:/' + kickstart +
           ' preseed/file=floppy://' + preseed +
           ' net.ifnames=0' +
           ' console=ttyS0' ]
    ubuntuStart = time()
    log( '* INSTALLING UBUNTU FROM', iso, 'ONTO', image )
    log( ' '.join( cmd ) )
    log( '* logging to', abspath( logfilename ) )
    params = {}
    if not LogToConsole:
        logfile = open( logfilename, 'w' )
        params = { 'stdout': logfile, 'stderr': logfile }
    vm = Popen( cmd, **params )
    log( '* Waiting for installation to complete')
    vm.wait()
    if not LogToConsole:
        logfile.close()
    elapsed = time() - ubuntuStart
    # Unmount iso and clean up
    ### DEBUGGING
    srun( 'ls -l ' + mnt )
    srun( 'umount ' + mnt )
    run( 'rmdir ' + mnt )
    if vm.returncode != 0:
        raise Exception( 'Ubuntu installation returned error %d' %
                          vm.returncode )
    log( '* UBUNTU INSTALLATION COMPLETED FOR', image )
    log( '* Ubuntu installation completed in %.2f seconds' % elapsed )


def boot( cow, kernel, initrd, logfile, memory=1024, cpuCores=1, partnum=1 ):
    """Boot qemu/kvm with a COW disk and local/user data store
       cow: COW disk path
       kernel: kernel path
       logfile: log file for pexpect object
       memory: memory size in MB
       cpuCores: number of CPU cores to use
       returns: pexpect object to qemu process"""
    # pexpect might not be installed until after depend() is called
    global pexpect
    if not pexpect:
        import pexpect
    class Spawn( pexpect.spawn ):
        "Subprocess is sudo, so we have to sudo kill it"
        def close( self, force=False ):
            srun( 'kill %d' % self.pid )
    arch = archFor( kernel )
    log( '* Detected kernel architecture', arch )
    if NoKVM:
        accel = 'tcg'
    else:
        accel = 'kvm'
    cmd = [ 'sudo', 'qemu-system-' + arch,
            '-machine accel=%s' % accel,
            '-nographic',
            '-netdev user,id=mnbuild',
            '-device virtio-net,netdev=mnbuild',
            '-m %s' % memory,
            '-k en-us',
            '-kernel', kernel,
            '-initrd', initrd,
            '-drive file=%s,if=virtio' % cow,
            '-append "root=/dev/vda%d init=/sbin/init'
            ' net.ifnames=0 console=ttyS0" ' % partnum ]
    log( cmd )
    if Forward:
        cmd += sum( [ [ '-redir', f ] for f in Forward ], [] )
    if cpuCores > 1:
        cmd += [ '-smp cores=%s' % cpuCores ]
    cmd = ' '.join( cmd )
    log( '* BOOTING VM FROM', cow )
    log( cmd )
    vm = Spawn( cmd, timeout=TIMEOUT, logfile=logfile )
    return vm


def login( vm, user='mininet', password='mininet' ):
    "Log in to vm (pexpect object)"
    log( '* Waiting for login prompt' )
    vm.expect( 'login: ' )
    log( '* Logging in' )
    vm.sendline( user )
    log( '* Waiting for password prompt' )
    vm.expect( 'Password: ' )
    log( '* Sending password' )
    vm.sendline( password )
    log( '* Waiting for login...' )


def removeNtpd( vm, prompt=Prompt, ntpPackage='ntp' ):
    "Remove ntpd and set clock immediately"
    log( '* Removing ntpd' )
    vm.sendline( 'sudo -n apt-get -qy remove ' + ntpPackage )
    vm.expect( prompt )
    # Try to make sure that it isn't still running
    vm.sendline( 'sudo -n pkill ntpd' )
    vm.expect( prompt )
    log( '* Getting seconds since epoch from this server' )
    # Note r'date +%s' specifies a format for 'date', not python!
    seconds = int( run( r'date +%s' ) )
    log( '* Setting VM clock' )
    vm.sendline( 'sudo -n date -s @%d' % seconds )


def sanityTest( vm ):
    "Run Mininet sanity test (pingall) in vm"
    vm.sendline( 'sudo -n mn --test pingall' )
    if vm.expect( [ ' 0% dropped', pexpect.TIMEOUT ], timeout=45 ) == 0:
        log( '* Sanity check OK' )
    else:
        log( '* Sanity check FAILED' )
        log( '* Sanity check output:' )
        log( vm.before )


def coreTest( vm, prompt=Prompt ):
    "Run core tests (make test) in VM"
    log( '* Making sure cgroups are mounted' )
    vm.sendline( 'sudo -n service cgroup-lite restart' )
    vm.expect( prompt )
    vm.sendline( 'sudo -n cgroups-mount' )
    vm.expect( prompt )
    log( '* Running make test' )
    vm.sendline( 'cd ~/mininet; sudo make test' )
    # We should change "make test" to report the number of
    # successful and failed tests. For now, we have to
    # know the time for each test, which means that this
    # script will have to change as we add more tests.
    for test in range( 0, 2 ):
        if vm.expect( [ 'OK.*\r\n', 'FAILED.*\r\n', pexpect.TIMEOUT ], timeout=180 ) == 0:
            log( '* Test', test, 'OK' )
        else:
            log( '* Test', test, 'FAILED' )
            log( '* Test', test, 'output:' )
            log( vm.before )


def installPexpect( vm, prompt=Prompt ):
    "install pexpect"
    vm.sendline( 'sudo -n apt-get -qy install python-pexpect' )
    vm.expect( prompt )


def noneTest( vm, prompt=Prompt ):
    "This test does nothing"
    installPexpect( vm, prompt )
    vm.sendline( 'echo' )


def examplesquickTest( vm, prompt=Prompt ):
    "Quick test of mininet examples"
    installPexpect( vm, prompt )
    vm.sendline( 'sudo -n python ~/mininet/examples/test/runner.py -v -quick' )


def examplesfullTest( vm, prompt=Prompt ):
    "Full (slow) test of mininet examples"
    installPexpect( vm, prompt )
    vm.sendline( 'sudo -n python ~/mininet/examples/test/runner.py -v' )


def walkthroughTest( vm, prompt=Prompt ):
    "Test mininet walkthrough"
    installPexpect( vm, prompt )
    vm.sendline( 'sudo -n python ~/mininet/mininet/test/test_walkthrough.py -v' )


def useTest( vm, prompt=Prompt ):
    "Use VM interactively - exit by pressing control-]"
    old = vm.logfile
    if old == stdout:
        # Avoid doubling every output character!
        log( '* Temporarily disabling logging to stdout' )
        vm.logfile = None
    log( '* Switching to interactive use - press control-] to exit' )
    vm.interact()
    if old == stdout:
        log( '* Restoring logging to stdout' )
        vm.logfile = stdout

# A convenient alias for use - 'run'; we might want to allow
# 'run' to take a parameter
runTest = useTest

def checkOutBranch( vm, branch, prompt=Prompt ):
    # This is a bit subtle; it will check out an existing branch (e.g. master)
    # if it exists; otherwise it will create a detached branch.
    # The branch will be rebased to its parent on origin.
    # This probably doesn't matter since we're running on a COW disk
    # anyway.
    vm.sendline( 'cd ~/mininet; git fetch origin ' + branch +
                 '; git checkout ' + branch +
                 '; git pull --rebase origin ' + branch )
    vm.expect( prompt )
    # Use install.sh since we may need to identify python version?
    vm.sendline( 'util/install.sh -n' )


def interact( vm, tests, pre='', post='', prompt=Prompt,
              clean=True):
    "Interact with vm, which is a pexpect object"
    login( vm )
    log( '* Waiting for login...' )
    vm.expect( prompt )
    log( '* Sending hostname command' )
    vm.sendline( 'hostname' )
    log( '* Waiting for output' )
    vm.expect( prompt )
    log( '* Fetching Mininet VM install script' )
    branch = Branch if Branch else 'master'
    vm.sendline( 'wget '
                 'https://raw.github.com/mininet/mininet/%s/util/vm/'
                 'install-mininet-vm.sh' % branch )
    vm.expect( prompt )
    log( '* Running VM install script' )
    installcmd = 'bash -v install-mininet-vm.sh'
    if Branch:
        installcmd += ' ' + Branch
    vm.sendline( installcmd )
    vm.expect ( 'password for mininet: ' )
    vm.sendline( 'mininet' )
    log( '* Waiting for script to complete... ' )
    # Long timeout since we may be on cloud CI
    # 30min for kvm, 1.5hr for emulation
    # TODO: detect installation errors
    timeout = 5200 if NoKVM else 1800
    vm.expect( 'Done preparing Mininet', timeout=timeout )
    log( '* Completed successfully' )
    vm.expect( prompt )
    version = getMininetVersion( vm )
    vm.expect( prompt )
    log( '* Mininet version: ', version )
    log( '* Testing Mininet' )
    runTests( vm, tests=tests, pre=pre, post=post )
    # Ubuntu adds this because we install via a serial console,
    # but we want the VM to boot via the VM console. Otherwise
    # we get the message 'error: terminal "serial" not found'
    log( '* Disabling serial console' )
    vm.sendline( "sudo sed -i -e 's/^GRUB_TERMINAL=serial/#GRUB_TERMINAL=serial/' "
                "/etc/default/grub; sudo update-grub" )
    vm.expect( prompt )
    if clean:
        log( '* Cleaning vm' )
        vm.sendline( '~/mininet/util/install.sh -d' )
    vm.expect( prompt )
    log( '* Shutting down' )
    vm.sendline( 'sync; sudo shutdown -h now' )
    log( '* Waiting for EOF/shutdown' )
    vm.read()
    log( '* Interaction complete' )
    return version


def cleanup():
    "Clean up leftover qemu-nbd processes and other junk"
    call( [ 'sudo', 'pkill', '-9', 'qemu-nbd' ] )


def convert( cow, basename ):
    """Convert a qcow2 disk to a vmdk and put it a new directory
       basename: base name for output vmdk file"""
    vmdk = basename + '.vmdk'
    log( '* Converting qcow2 to vmdk' )
    run( 'qemu-img convert -f qcow2 -O vmdk %s %s' % ( cow, vmdk ) )
    return vmdk


# Template for OVF - a very verbose format!
# In the best of all possible worlds, we might use an XML
# library to generate this, but a template is easier and
# possibly more concise!
# Warning: XML file cannot begin with a newline!

OVFTemplate = """<?xml version="1.0"?>
<Envelope ovf:version="1.0" xml:lang="en-US"
    xmlns="http://schemas.dmtf.org/ovf/envelope/1"
    xmlns:ovf="http://schemas.dmtf.org/ovf/envelope/1"
    xmlns:rasd="http://schemas.dmtf.org/wbem/wscim/1/cim-schema/2/CIM_ResourceAllocationSettingData"
    xmlns:vssd="http://schemas.dmtf.org/wbem/wscim/1/cim-schema/2/CIM_VirtualSystemSettingData"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
<References>
<File ovf:href="%(diskname)s" ovf:id="file1" ovf:size="%(filesize)d"/>
</References>
<DiskSection>
<Info>Virtual disk information</Info>
<Disk ovf:capacity="%(disksize)d" ovf:capacityAllocationUnits="byte"
    ovf:diskId="vmdisk1" ovf:fileRef="file1"
    ovf:format="http://www.vmware.com/interfaces/specifications/vmdk.html#streamOptimized"/>
</DiskSection>
<NetworkSection>
<Info>The list of logical networks</Info>
<Network ovf:name="nat">
<Description>The nat  network</Description>
</Network>
</NetworkSection>
<VirtualSystem ovf:id="%(vmname)s">
<Info>%(vminfo)s (%(name)s)</Info>
<Name>%(vmname)s</Name>
<OperatingSystemSection ovf:id="%(osid)d">
<Info>The kind of installed guest operating system</Info>
<Description>%(osname)s</Description>
</OperatingSystemSection>
<VirtualHardwareSection>
<Info>Virtual hardware requirements</Info>
<Item>
<rasd:AllocationUnits>hertz * 10^6</rasd:AllocationUnits>
<rasd:Description>Number of Virtual CPUs</rasd:Description>
<rasd:ElementName>%(cpus)s virtual CPU(s)</rasd:ElementName>
<rasd:InstanceID>1</rasd:InstanceID>
<rasd:ResourceType>3</rasd:ResourceType>
<rasd:VirtualQuantity>%(cpus)s</rasd:VirtualQuantity>
</Item>
<Item>
<rasd:AllocationUnits>byte * 2^20</rasd:AllocationUnits>
<rasd:Description>Memory Size</rasd:Description>
<rasd:ElementName>%(mem)dMB of memory</rasd:ElementName>
<rasd:InstanceID>2</rasd:InstanceID>
<rasd:ResourceType>4</rasd:ResourceType>
<rasd:VirtualQuantity>%(mem)d</rasd:VirtualQuantity>
</Item>
<Item>
<rasd:Address>0</rasd:Address>
<rasd:Caption>scsiController0</rasd:Caption>
<rasd:Description>SCSI Controller</rasd:Description>
<rasd:ElementName>scsiController0</rasd:ElementName>
<rasd:InstanceID>4</rasd:InstanceID>
<rasd:ResourceSubType>lsilogic</rasd:ResourceSubType>
<rasd:ResourceType>6</rasd:ResourceType>
</Item>
<Item>
<rasd:AddressOnParent>0</rasd:AddressOnParent>
<rasd:ElementName>disk1</rasd:ElementName>
<rasd:HostResource>ovf:/disk/vmdisk1</rasd:HostResource>
<rasd:InstanceID>11</rasd:InstanceID>
<rasd:Parent>4</rasd:Parent>
<rasd:ResourceType>17</rasd:ResourceType>
</Item>
<Item>
<rasd:AddressOnParent>2</rasd:AddressOnParent>
<rasd:AutomaticAllocation>true</rasd:AutomaticAllocation>
<rasd:Connection>nat</rasd:Connection>
<rasd:Description>E1000 ethernet adapter on nat</rasd:Description>
<rasd:ElementName>ethernet0</rasd:ElementName>
<rasd:InstanceID>12</rasd:InstanceID>
<rasd:ResourceSubType>E1000</rasd:ResourceSubType>
<rasd:ResourceType>10</rasd:ResourceType>
</Item>
<Item>
<rasd:Address>0</rasd:Address>
<rasd:Caption>usb</rasd:Caption>
<rasd:Description>USB Controller</rasd:Description>
<rasd:ElementName>usb</rasd:ElementName>
<rasd:InstanceID>9</rasd:InstanceID>
<rasd:ResourceType>23</rasd:ResourceType>
</Item>
</VirtualHardwareSection>
</VirtualSystem>
</Envelope>
"""


def generateOVF( name, osname, osid, diskname, disksize, mem=1024, cpus=1,
                 vmname='Mininet-VM', vminfo='A Mininet Virtual Machine' ):
    """Generate (and return) OVF file "name.ovf"
       name: root name of OVF file to generate
       osname: OS name for OVF (Ubuntu | Ubuntu 64-bit)
       osid: OS ID for OVF (93 | 94 )
       diskname: name of disk file
       disksize: size of virtual disk in bytes
       mem: VM memory size in MB
       cpus: # of virtual CPUs
       vmname: Name for VM (default name when importing)
       vmimfo: Brief description of VM for OVF"""
    ovf = name + '.ovf'
    filesize = stat( diskname )[ ST_SIZE ]
    params = dict( osname=osname, osid=osid, diskname=diskname,
                   filesize=filesize, disksize=disksize, name=name,
                   mem=mem, cpus=cpus, vmname=vmname, vminfo=vminfo )
    xmltext = OVFTemplate % params
    with open( ovf, 'w+' ) as f:
        f.write( xmltext )
    return ovf


def qcow2size( qcow2 ):
    "Return virtual disk size (in bytes) of qcow2 image"
    output = check_output( [ 'qemu-img', 'info', qcow2 ] )
    try:
        assert 'format: qcow' in output
        bytes = int( re.findall( '(\d+) bytes', output )[ 0 ] )
    except:
        raise Exception( 'Could not determine size of %s' % qcow2 )
    return bytes


def build( flavor='raring32server', tests=None, pre='', post='', memory=1024 ):
    """Build a Mininet VM; return vmdk and vdisk size
       tests: tests to run
       pre: command line to run in VM before tests
       post: command line to run in VM after tests
       prompt: shell prompt (default '$ ')
       memory: memory size in MB"""
    global LogFile, Zip, Chown
    start = time()
    lstart = localtime()
    date = strftime( '%y%m%d-%H-%M-%S', lstart)
    ovfdate = strftime( '%y%m%d', lstart )
    dir = 'mn-%s-%s' % ( flavor, date )
    if Branch:
        dir = 'mn-%s-%s-%s' % ( Branch, flavor, date )
    try:
        os.mkdir( dir)
    except:
        raise Exception( "Failed to create build directory %s" % dir )
    if Chown:
        run( 'chown %s %s' % ( Chown, dir ) )
    os.chdir( dir )
    LogFile = open( 'build.log', 'w' )
    log( '* Logging to', abspath( LogFile.name ) )
    log( '* Created working directory', dir )
    image, kernel, initrd, partnum = findBaseImage( flavor )
    basename = 'mininet-' + flavor
    volume = basename + '.qcow2'
    run( 'qemu-img create -f qcow2 -b %s %s' % ( image, volume ) )
    log( '* VM image for', flavor, 'created as', volume )
    if LogToConsole:
        logfile = stdout
    else:
        logfile = open( flavor + '.log', 'w+' )
    log( '* Logging results to', abspath( logfile.name ) )
    vm = boot( volume, kernel, initrd, logfile, memory=memory, partnum=partnum )
    version = interact( vm, tests=tests, pre=pre, post=post )
    size = qcow2size( volume )
    arch = archFor( flavor )
    vmdk = convert( volume, basename='mininet-vm-' + arch )
    if not SaveQCOW2:
        log( '* Removing qcow2 volume', volume )
        os.remove( volume )
    log( '* Converted VM image stored as', abspath( vmdk ) )
    ovfname = 'mininet-%s-%s-%s' % ( version, ovfdate, OSVersion( flavor ) )
    osname, osid = OVFOSNameID( flavor )
    ovf = generateOVF( name=ovfname, osname=osname, osid=osid,
                       diskname=vmdk, disksize=size )
    log( '* Generated OVF descriptor file', ovf )
    if Zip:
        log( '* Generating .zip file' )
        run( 'zip %s-ovf.zip %s %s' % ( ovfname, ovf, vmdk ) )
    end = time()
    elapsed = end - start
    log( '* Results logged to', abspath( logfile.name ) )
    log( '* Completed in %.2f seconds' % elapsed )
    log( '* %s VM build DONE!!!!! :D' % flavor )
    os.chdir( '..' )


def runTests( vm, tests=None, pre='', post='', prompt=Prompt, uninstallNtpd=False ):
    "Run tests (list) in vm (pexpect object)"
    # We disable ntpd and set the time so that ntpd won't be
    # messing with the time during tests. Set to true for a COW
    # disk and False for a non-COW disk.
    if uninstallNtpd:
        removeNtpd( vm )
        vm.expect( prompt )
    if Branch:
        checkOutBranch( vm, branch=Branch )
        vm.expect( prompt )
    if not tests:
        tests = []
    if pre:
        log( '* Running command', pre )
        vm.sendline( pre )
        vm.expect( prompt )
    testfns = testDict()
    if tests:
        log( '* Running tests' )
    for test in tests:
        if test not in testfns:
            raise Exception( 'Unknown test: ' + test )
        log( '* Running test', test )
        fn = testfns[ test ]
        fn( vm )
        vm.expect( prompt )
    if post:
        log( '* Running post-test command', post )
        vm.sendline( post )
        vm.expect( prompt )

def getMininetVersion( vm ):
    "Run mn to find Mininet version in VM"
    vm.sendline( '(cd ~/mininet; PYTHONPATH=. bin/mn --version)' )
    # Eat command line echo, then read output line
    vm.readline()
    version = vm.readline().strip()
    return version


def bootAndRun( image, prompt=Prompt, memory=1024, cpuCores=1, outputFile=None,
                runFunction=None, **runArgs ):
    """Boot and test VM
       tests: list of tests to run
       pre: command line to run in VM before tests
       post: command line to run in VM after tests
       prompt: shell prompt (default '$ ')
       memory: VM memory size in MB
       cpuCores: number of CPU cores to use"""
    bootTestStart = time()
    basename = path.basename( image )
    image = abspath( image )
    tmpdir = mkdtemp( prefix='test-' + basename )
    log( '* Using tmpdir', tmpdir )
    cow = path.join( tmpdir, basename + '.qcow2' )
    log( '* Creating COW disk', cow )
    run( 'qemu-img create -f qcow2 -b %s %s' % ( image, cow ) )
    log( '* Extracting kernel and initrd' )
    kernel, initrd, partnum = extractKernel(
        image, flavor=basename, imageDir=tmpdir )
    if LogToConsole:
        logfile = stdout
    else:
        logfile = NamedTemporaryFile( prefix=basename,
                                      suffix='.testlog', delete=False )
    log( '* Logging VM output to', logfile.name )
    vm = boot( cow=cow, kernel=kernel, initrd=initrd, logfile=logfile,
               memory=memory, cpuCores=cpuCores, partnum=partnum )
    login( vm )
    log( '* Waiting for prompt after login' )
    vm.expect( prompt )
    # runFunction should begin with sendline and should eat its last prompt
    if runFunction:
        runFunction( vm, **runArgs )
    log( '* Shutting down' )
    vm.sendline( 'sudo -n shutdown -h now ' )
    log( '* Waiting for shutdown' )
    vm.wait()
    if outputFile:
        log( '* Saving temporary image to %s' % outputFile )
        convert( cow, outputFile )
    log( '* Removing temporary dir', tmpdir )
    srun( 'rm -rf ' + tmpdir )
    elapsed = time() - bootTestStart
    log( '* Boot and test completed in %.2f seconds' % elapsed )


def buildFlavorString():
    "Return string listing valid build flavors"
    return 'valid build flavors: %s' % ' '.join( sorted( isoURLs ) )


def testDict():
    "Return dict of tests in this module"
    suffix = 'Test'
    trim = len( suffix )
    fdict = dict( [ ( fname[ : -trim ], f ) for fname, f in
                    inspect.getmembers( modules[ __name__ ],
                                    inspect.isfunction )
                  if fname.endswith( suffix ) ] )
    return fdict


def testString():
    "Return string listing valid tests"
    tests = [ '%s <%s>' % ( name, func.__doc__ )
              for name, func in testDict().items() ]
    return 'valid tests: %s' % ', '.join( tests )


def parseArgs():
    "Parse command line arguments and run"
    global LogToConsole, NoKVM, Branch, Zip, TIMEOUT, Forward, Chown
    parser = argparse.ArgumentParser( description='Mininet VM build script',
                                      epilog='' )
    parser.add_argument( '-v', '--verbose', action='store_true',
                        help='send VM output to console rather than log file' )
    parser.add_argument( '-d', '--depend', action='store_true',
                         help='install dependencies for this script' )
    parser.add_argument( '-l', '--list', action='store_true',
                         help='list valid build flavors and tests' )
    parser.add_argument( '-c', '--clean', action='store_true',
                         help='clean up leftover build junk (e.g. qemu-nbd)' )
    parser.add_argument( '-q', '--qcow2', action='store_true',
                         help='save qcow2 image rather than deleting it' )
    parser.add_argument( '-n', '--nokvm', action='store_true',
                         help="Don't use kvm - use tcg emulation instead" )
    parser.add_argument( '-m', '--memory', metavar='MB', type=int,
                        default=1024, help='VM memory size in MB' )
    parser.add_argument( '-i', '--image', metavar='image', default=[],
                         action='append',
                         help='Boot and test an existing VM image' )
    parser.add_argument( '-t', '--test', metavar='test', default=[],
                         action='append',
                         help='specify a test to run; ' + testString() )
    parser.add_argument( '-w', '--timeout', metavar='timeout', type=int,
                            default=0, help='set expect timeout' )
    parser.add_argument( '-r', '--run', metavar='cmd', default='',
                         help='specify a command line to run before tests' )
    parser.add_argument( '-p', '--post', metavar='cmd', default='',
                         help='specify a command line to run after tests' )
    parser.add_argument( '-b', '--branch', metavar='branch',
                         help='branch to install and/or check out and test' )
    parser.add_argument( 'flavor', nargs='*',
                         help='VM flavor(s) to build; ' + buildFlavorString() )
    parser.add_argument( '-z', '--zip', action='store_true',
                         help='archive .ovf and .vmdk into .zip file' )
    parser.add_argument( '-o', '--out',
                         help='output file for test image (vmdk)' )
    parser.add_argument( '-f', '--forward', default=[], action='append',
                         help='forward VM ports to local server, e.g. tcp:5555::22' )
    parser.add_argument( '-u', '--chown', metavar='user',
                         help='specify an owner for build directory' )
    args = parser.parse_args()
    if args.depend:
        depend()
    if args.list:
        print( buildFlavorString() )
    if args.clean:
        cleanup()
    if args.verbose:
        LogToConsole = True
    if args.nokvm:
        NoKVM = True
    if args.branch:
        Branch = args.branch
    if args.zip:
        Zip = True
    if args.timeout:
        TIMEOUT = args.timeout
    if args.forward:
        Forward = args.forward
    if not args.test and not args.run and not args.post:
        args.test = [ 'sanity', 'core' ]
    if args.chown:
        Chown = args.chown
    for flavor in args.flavor:
        if flavor not in isoURLs:
            print( "Unknown build flavor:", flavor )
            print( buildFlavorString() )
            break
        try:
            build( flavor, tests=args.test, pre=args.run, post=args.post,
                   memory=args.memory )
        except Exception as e:
            log( '* BUILD FAILED with exception: ', e )
            print_exc( e )
            exit( 1 )
    for image in args.image:
        bootAndRun( image, runFunction=runTests, tests=args.test, pre=args.run,
                    post=args.post, memory=args.memory, outputFile=args.out,
                    uninstallNtpd=True  )
    if not ( args.depend or args.list or args.clean or args.flavor
             or args.image ):
        parser.print_help()


if __name__ == '__main__':
    parseArgs()
