#!/usr/bin/python

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
    -> make codecheck
    -> make test

    release
    -> shut down VM
    -> shrink-wrap VM
    -> upload to storage

"""

import os
from os import stat, path
from stat import ST_MODE
from os.path import abspath
from sys import exit, argv
from glob import glob
from subprocess import check_output, call, Popen
from tempfile import mkdtemp
from time import time, strftime, localtime
import argparse

pexpect = None  # For code check - imported dynamically

# boot can be slooooow!!!! need to debug/optimize somehow
TIMEOUT=600

VMImageDir = os.environ[ 'HOME' ] + '/vm-images'

isoURLs = {
    'precise32server':
    'http://mirrors.kernel.org/ubuntu-releases/12.04/'
    'ubuntu-12.04.3-server-i386.iso',
    'precise64server':
    'http://mirrors.kernel.org/ubuntu-releases/12.04/'
    'ubuntu-12.04.3-server-amd64.iso',
    'quantal32server':
    'http://mirrors.kernel.org/ubuntu-releases/12.10/'
    'ubuntu-12.10-server-i386.iso',
    'quantal64server':
    'http://mirrors.kernel.org/ubuntu-releases/12.10/'
    'ubuntu-12.10-server-amd64.iso',
    'raring32server':
    'http://mirrors.kernel.org/ubuntu-releases/13.04/'
    'ubuntu-13.04-server-i386.iso',
    'raring64server':
    'http://mirrors.kernel.org/ubuntu-releases/13.04/'
    'ubuntu-13.04-server-amd64.iso',
}

logStartTime = time()

def log( *args, **kwargs ):
    """Simple log function: log( message along with local and elapsed time
       cr: False/0 for no CR"""
    cr = kwargs.get( 'cr', True )
    elapsed = time() - logStartTime
    clocktime = strftime( '%H:%M:%S', localtime() )
    msg = ' '.join( str( arg ) for arg in args )
    output = '%s [ %.3f ] %s' % ( clocktime, elapsed, msg )
    if cr:
        print output
    else:
        print output,


def run( cmd, **kwargs ):
    "Convenient interface to check_output"
    log( '-', cmd )
    cmd = cmd.split()
    return check_output( cmd, **kwargs )


def srun( cmd, **kwargs ):
    "Run + sudo"
    return run( 'sudo ' + cmd, **kwargs )


def depend():
    "Install package dependencies"
    log( '* Installing package dependencies' )
    run( 'sudo apt-get -y update' )
    run( 'sudo apt-get install -y'
         ' kvm cloud-utils genisoimage qemu-kvm qemu-utils'
         ' e2fsprogs '
         ' landscape-client'
         ' python-setuptools' )
    run( 'sudo easy_install pexpect' )


def popen( cmd ):
    "Convenient interface to popen"
    log( cmd )
    cmd = cmd.split()
    return Popen( cmd )


def remove( fname ):
    "rm -f fname"
    return run( 'rm -f %s' % fname )


def findiso( flavor ):
    "Find iso, fetching it if it's not there already"
    url = isoURLs[ flavor ]
    name = path.basename( url )
    iso = path.join( VMImageDir, name )
    if not path.exists( iso ) or ( stat( iso )[ ST_MODE ] & 0777 != 0444 ):
        log( '* Retrieving', url )
        run( 'curl -C - -o %s %s' % ( iso, url ) )
        if 'ISO' not in run( 'file ' + iso ):
            os.remove( iso )
            raise Exception( 'findiso: could not download iso from ' + url )
        # Write-protect iso, signaling it is complete
        log( '* Write-protecting iso', iso)
        os.chmod( iso, 0444 )
    log( '* Using iso', iso )
    return iso


def attachNBD( cow, flags='' ):
    """Attempt to attach a COW disk image and return its nbd device
        flags: additional flags for qemu-nbd (e.g. -r for readonly)"""
    # qemu-nbd requires an absolute path
    cow = abspath( cow )
    log( '* Checking for unused /dev/nbdX device ' )
    for i in range ( 0, 63 ):
        nbd = '/dev/nbd%d' % i
        # Check whether someone's already messing with that device
        if call( [ 'pgrep', '-f', nbd ] ) == 0:
            continue
        srun( 'modprobe nbd max-part=64' )
        srun( 'qemu-nbd %s -c %s %s' % ( flags, nbd, cow ) )
        print
        return nbd
    raise Exception( "Error: could not find unused /dev/nbdX device" )


def detachNBD( nbd ):
    "Detatch an nbd device"
    srun( 'qemu-nbd -d ' + nbd )


def extractKernel( image, flavor ):
    "Extract kernel and initrd from base image"
    kernel = path.join( VMImageDir, flavor + '-vmlinuz' )
    initrd = path.join( VMImageDir, flavor + '-initrd' )
    if path.exists( kernel ) and ( stat( image )[ ST_MODE ] & 0777 ) == 0444:
        # If kernel is there, then initrd should also be there
        return kernel, initrd
    log( '* Extracting kernel to', kernel )
    nbd = attachNBD( image, flags='-r' )
    print srun( 'partx ' + nbd )
    # Assume kernel is in partition 1/boot/vmlinuz*generic for now
    part = nbd + 'p1'
    mnt = mkdtemp()
    srun( 'mount -o ro %s %s' % ( part, mnt  ) )
    kernsrc = glob( '%s/boot/vmlinuz*generic' % mnt )[ 0 ]
    initrdsrc = glob( '%s/boot/initrd*generic' % mnt )[ 0 ]
    srun( 'cp %s %s' % ( initrdsrc, initrd ) )
    srun( 'chmod 0444 ' + initrd )
    srun( 'cp %s %s' % ( kernsrc, kernel ) )
    srun( 'chmod 0444 ' + kernel )
    srun( 'umount ' + mnt )
    run( 'rmdir ' + mnt )
    detachNBD( nbd )
    return kernel, initrd


def findBaseImage( flavor, size='8G' ):
    "Return base VM image and kernel, creating them if needed"
    image = path.join( VMImageDir, flavor + '-base.qcow2' )
    if path.exists( image ):
        # Detect race condition with multiple builds
        perms = stat( image )[ ST_MODE ] & 0777
        if perms != 0444:
            raise Exception( 'Error - %s is writable ' % image +
                            '; are multiple builds running?' )
    else:
        # We create VMImageDir here since we are called first
        run( 'mkdir -p %s' % VMImageDir )
        iso = findiso( flavor )
        log( '* Creating image file', image )
        run( 'qemu-img create -f qcow2 %s %s' % ( image, size ) )
        installUbuntu( iso, image )
        # Write-protect image, also signaling it is complete
        log( '* Write-protecting image', image)
        os.chmod( image, 0444 )
    kernel, initrd = extractKernel( image, flavor )
    log( '* Using base image', image, 'and kernel', kernel )
    return image, kernel, initrd


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
#System authorization infomation
auth  --useshadow  --enablemd5
#Firewall configuration
firewall --disabled
#Do not configure the X Window System
skipx
"""

# Tell the Ubuntu/Debian installer to stop asking stupid questions

PreseedText = """
d-i mirror/country string manual
d-i mirror/http/hostname string mirrors.kernel.org
d-i mirror/http/directory string /ubuntu
d-i mirror/http/proxy string
d-i partman/confirm_write_new_label boolean true
d-i partman/choose_partition select finish
d-i partman/confirm boolean true
d-i partman/confirm_nooverwrite boolean true
d-i user-setup/allow-password-weak boolean true
d-i finish-install/reboot_in_progress note
d-i debian-installer/exit/poweroff boolean true
"""

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


def kvmFor( filepath ):
    "Guess kvm version for file path"
    name = path.basename( filepath )
    if '64' in name:
        kvm = 'qemu-system-x86_64'
    elif 'i386' in name or '32' in name:
        kvm = 'qemu-system-i386'
    else:
        log( "Error: can't discern CPU for file name", name )
        exit( 1 )
    return kvm


def installUbuntu( iso, image, logfilename='install.log' ):
    "Install Ubuntu from iso onto image"
    kvm = kvmFor( iso )
    floppy, kickstart, preseed = makeKickstartFloppy()
    # Mount iso so we can use its kernel
    mnt = mkdtemp()
    srun( 'mount %s %s' % ( iso, mnt ) )
    kernel = path.join( mnt, 'install/vmlinuz' )
    initrd = path.join( mnt, 'install/initrd.gz' )
    cmd = [ 'sudo', kvm,
           '-machine', 'accel=kvm',
           '-nographic',
           '-netdev', 'user,id=mnbuild',
           '-device', 'virtio-net,netdev=mnbuild',
           '-m', '1024',
           '-k', 'en-us',
           '-fda', floppy,
           '-drive', 'file=%s,if=virtio' % image,
           '-cdrom', iso,
           '-kernel', kernel,
           '-initrd', initrd,
           '-append',
           ' ks=floppy:/' + kickstart +
           ' preseed/file=floppy://' + preseed +
           ' console=ttyS0' ]
    ubuntuStart = time()
    log( '* INSTALLING UBUNTU FROM', iso, 'ONTO', image )
    log( ' '.join( cmd ) )
    log( '* logging to', abspath( logfilename ) )
    logfile = open( logfilename, 'w' )
    vm = Popen( cmd, stdout=logfile, stderr=logfile )
    log( '* Waiting for installation to complete')
    vm.wait()
    logfile.close()
    elapsed = time() - ubuntuStart
    # Unmount iso and clean up
    srun( 'umount ' + mnt )
    run( 'rmdir ' + mnt )
    log( '* UBUNTU INSTALLATION COMPLETED FOR', image )
    log( '* Ubuntu installation completed in %.2f seconds ' % elapsed )


def boot( cow, kernel, initrd, logfile ):
    """Boot qemu/kvm with a COW disk and local/user data store
       cow: COW disk path
       kernel: kernel path
       logfile: log file for pexpect object
       returns: pexpect object to qemu process"""
    # pexpect might not be installed until after depend() is called
    global pexpect
    import pexpect
    kvm = kvmFor( kernel )
    cmd = [ 'sudo', kvm,
            '-machine accel=kvm',
            '-nographic',
            '-netdev user,id=mnbuild',
            '-device virtio-net,netdev=mnbuild',
            '-m 1024',
            '-k en-us',
            '-kernel', kernel,
            '-initrd', initrd,
            '-drive file=%s,if=virtio' % cow,
            '-append "root=/dev/vda1 init=/sbin/init console=ttyS0" ' ]
    cmd = ' '.join( cmd )
    log( '* BOOTING VM FROM', cow )
    log( cmd )
    vm = pexpect.spawn( cmd, timeout=TIMEOUT, logfile=logfile )
    return vm


def interact( vm ):
    "Interact with vm, which is a pexpect object"
    prompt = '\$ '
    log( '* Waiting for login prompt' )
    vm.expect( 'login: ' )
    log( '* Logging in' )
    vm.sendline( 'mininet' )
    log( '* Waiting for password prompt' )
    vm.expect( 'Password: ' )
    log( '* Sending password' )
    vm.sendline( 'mininet' )
    log( '* Waiting for login...' )
    vm.expect( prompt )
    log( '* Sending hostname command' )
    vm.sendline( 'hostname' )
    log( '* Waiting for output' )
    vm.expect( prompt )
    log( '* Fetching Mininet VM install script' )
    vm.sendline( 'wget '
                 'https://raw.github.com/mininet/mininet/master/util/vm/'
                 'install-mininet-vm.sh' )
    vm.expect( prompt )
    log( '* Running VM install script' )
    vm.sendline( 'bash install-mininet-vm.sh' )
    vm.expect ( 'password for mininet: ' )
    vm.sendline( 'mininet' )
    log( '* Waiting for script to complete... ' )
    # Gigantic timeout for now ;-(
    vm.expect( 'Done preparing Mininet', timeout=3600 )
    log( '* Completed successfully' )
    vm.expect( prompt )
    log( '* Testing Mininet' )
    vm.sendline( 'sudo mn --test pingall' )
    if vm.expect( [ ' 0% dropped', pexpect.TIMEOUT ], timeout=45 ) == 0:
        log( '* Sanity check OK' )
    else:
        log( '* Sanity check FAILED' )
    vm.expect( prompt )
    log( '* Making sure cgroups are mounted' )
    vm.sendline( 'sudo service cgroup-lite restart' )
    vm.expect( prompt )
    vm.sendline( 'sudo cgroups-mount' )
    vm.expect( prompt )
    log( '* Running make test' )
    vm.sendline( 'cd ~/mininet; sudo make test' )
    # We should change "make test" to report the number of
    # successful and failed tests. For now, we have to
    # know the time for each test, which means that this
    # script will have to change as we add more tests.
    for test in range( 0, 2 ):
        if vm.expect( [ 'OK', 'FAILED', pexpect.TIMEOUT ], timeout=180 ) == 0:
            log( '* Test', test, 'OK' )
        else:
            log( '* Test', test, 'FAILED' )
    vm.expect( prompt )
    log( '* Shutting down' )
    vm.sendline( 'sync; sudo shutdown -h now' )
    log( '* Waiting for EOF/shutdown' )
    vm.read()
    log( '* Interaction complete' )


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


# Template for virt-image(5) file

VirtImageXML = """
<?xml version="1.0" encoding="UTF-8"?>
<image>
    <name>%s</name>
    <domain>
        <boot type="hvm">
            <guest>
                <arch>%s/arch>
            </guest>
            <os>
                <loader dev="hd"/>
            </os>
            <drive disk="root.raw" target="hda"/>
        </boot>
        <devices>
            <vcpu>1</vcpu>
            <memory>%s</memory>
            <interface/>
            <graphics/>
        </devices>
    </domain>
        <storage>
            <disk file="%s" size="%s" format="vmdk"/>
        </storage>
</image>
"""

def genVirtImage( name, mem, diskname, disksize ):
    "Generate and return virt-image file name.xml"
    # Our strategy is going to be: create a
    # virt-image file and then use virt-convert to convert
    # it to an .ovf file
    xmlfile = name + '.xml'
    xmltext = VirtImageXML % ( name, mem, diskname, disksize )
    with open( xmlfile, 'w+' ) as f:
        f.write( xmltext )
    return xmlfile


def build( flavor='raring32server' ):
    "Build a Mininet VM"
    start = time()
    date = strftime( '%y%m%d-%H-%M-%S', localtime())
    dir = 'mn-%s-%s' % ( flavor, date )
    try:
        os.mkdir( dir )
    except:
        raise Exception( "Failed to create build directory %s" % dir )
    os.chdir( dir )
    log( '* Created working directory', dir )
    image, kernel, initrd = findBaseImage( flavor )
    volume = flavor + '.qcow2'
    run( 'qemu-img create -f qcow2 -b %s %s' % ( image, volume ) )
    log( '* VM image for', flavor, 'created as', volume )
    logfile = open( flavor + '.log', 'w+' )
    log( '* Logging results to', abspath( logfile.name ) )
    vm = boot( volume, kernel, initrd, logfile )
    interact( vm )
    vmdk = convert( volume, basename=flavor )
    log( '* Removing qcow2 volume', volume )
    os.remove( volume )
    log( '* Converted VM image stored as', abspath( vmdk ) )
    end = time()
    elapsed = end - start
    log( '* Results logged to', abspath( logfile.name ) )
    log( '* Completed in %.2f seconds' % elapsed )
    log( '* %s VM build DONE!!!!! :D' % flavor )
    os.chdir( '..' )


def listFlavors():
    "List valid build flavors"
    print '\nvalid build flavors:', ' '.join( isoURLs ), '\n'


def parseArgs():
    "Parse command line arguments and run"
    parser = argparse.ArgumentParser( description='Mininet VM build script' )
    parser.add_argument( '--depend', action='store_true',
                         help='install dependencies for this script' )
    parser.add_argument( '--list', action='store_true',
                         help='list valid build flavors' )
    parser.add_argument( '--clean', action='store_true',
                         help='clean up leftover build junk (e.g. qemu-nbd)' )
    parser.add_argument( 'flavor', nargs='*',
                         help='VM flavor to build (e.g. raring32server)' )
    args = parser.parse_args( argv )
    if args.depend:
        depend()
    if args.list:
        listFlavors()
    if args.clean:
        cleanup()
    flavors = args.flavor[ 1: ]
    for flavor in flavors:
        if flavor not in isoURLs:
            parser.print_help()
            listFlavors()
            break
        # try:
        build( flavor )
        # except Exception as e:
        # log( '* BUILD FAILED with exception: ', e )
        # exit( 1 )
    if not ( args.depend or args.list or args.clean or flavors ):
        parser.print_help()
        listFlavors()

if __name__ == '__main__':
    parseArgs()
