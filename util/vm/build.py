#!/usr/bin/python

"""
build.py: build a Mininet VM

Basic idea:

    prepare
    - download cloud image if it's missing
    - write-protect it

    build
    -> create cow disk for vm
    -> boot it in qemu/kvm with text /serial console
    -> install Mininet

    test
    -> make codecheck
    -> make test

    release
    -> shut down VM
    -> shrink-wrap VM
    -> upload to storage


Notes du jour:

- our infrastructure is currently based on 12.04 LTS, so we
  can't rely on cloud-localds which is only in 12.10+

- as a result, we should download the tar image, extract it,
  and boot with tty0 as the console (I think)

- and we'll manually add the mininet user to it
 
- and use pexpect to interact with it on the serial console

Something to think about:

Maybe download the cloud image and customize it so that
it is an actual usable/bootable image???

More notes:

We really want a full, partitioned disk image!

This means we want to use the disk1.image file ???

However, this means that we will need to change the grub2
configuratin to use a serial console.

/etc/default/grub:
    GRUB_TERMINAL=serial
    GRUB_SERIAL_COMMAND="serial --unit=0 --speed=38400 --word=8 --parity=no --stop=1"
    BOOT_IMAGE="console=ttyS0"
    
# grub2-mkconfig -o /boot/grub2/grub.cfg

by the way, we should use wget -c

"""

import os
from os import stat
from stat import ST_MODE
from os.path import exists, splitext, abspath, realpath
from sys import exit, argv
from glob import glob
from urllib import urlretrieve
from subprocess import check_output, call, Popen, PIPE
from tempfile import mkdtemp
from time import time
import argparse

pexpect = None  # For code check - imported dynamically


# boot can be slooooow!!!! need to debug/optimize somehow
TIMEOUT=600

VMImageDir = os.environ[ 'HOME' ] + '/vm-images'

ImageURLBase = {
    'raring32server':
    'http://cloud-images.ubuntu.com/raring/current/'
    'raring-server-cloudimg-i386',
    'raring64server':
    'http://cloud-images.ubuntu.com/raring/current/'
    'raring-server-cloudimg-amd64'
}


def run( cmd, **kwargs ):
    "Convenient interface to check_output"
    print cmd
    cmd = cmd.split()
    return check_output( cmd, **kwargs )


def srun( cmd, **kwargs ):
    "Run + sudo"
    return run( 'sudo ' + cmd, **kwargs )


def depend():
    "Install packagedependencies"
    print '* Installing package dependencies'
    run( 'sudo apt-get -y update' )
    run( 'sudo apt-get install -y'
         ' kvm cloud-utils genisoimage qemu-kvm qemu-utils'
         ' e2fsprogs '
         ' landscape-client'
         ' python-setuptools' )
    run( 'sudo easy_install pexpect' )


def popen( cmd ):
    "Convenient interface to popen"
    print cmd
    cmd = cmd.split()
    return Popen( cmd )


def remove( fname ):
    "rm -f fname"
    return run( 'rm -f %s' % fname )



def imageURL( image ):
    "Return base URL for VM image"
    return ImageURLBase[ image ]


def imagePath( image ):
    "Return base pathname for VM image files"
    url = imageURL( image )
    fname = url.split( '/' )[ -1 ]
    path = os.path.join( VMImageDir, fname )
    return path


def fetchImage( image, path=None ):
    "Fetch base VM image if it's not there already"
    if not path:
        path = imagePath( image )
    tgz = path + '.disk1.img'
    disk = path + '.img'
    kernel = path + '-vmlinuz-generic'
    if exists( disk ) and exists( kernel ):
        print '* Found', disk, 'and', kernel
        # Detect race condition with multiple builds
        perms = stat( disk )[ ST_MODE ] & 0777
        if perms != 0444:
            raise Exception( 'Error - %s is writable ' % disk +
                             '; are multiple builds running?' )
    else:
        dir = os.path.dirname( path )
        run( 'mkdir -p %s' % dir )
        if not os.path.exists( tgz ):
            url = imageURL( image ) + '.tar.gz'
            print '* Retrieving', url
            urlretrieve( url, tgz )
        print '* Extracting', tgz
        run( 'tar -C %s -xzf %s' % ( dir, tgz ) )
        # Write-protect disk image so it remains pristine;
        # We will not use it directly but will use a COW disk
        print '* Write-protecting disk image', disk
        os.chmod( disk, 0444 )
    return disk, kernel


def addTo( file, line ):
    "Add line to file if it's not there already"
    if call( [ 'sudo', 'grep', line, file ] ) != 0:
        call( 'echo "%s" | sudo tee -a %s' % ( line, file ), shell=True )


def disableCloud( bind ):
    "Disable cloud junk for disk mounted at bind"
    print '* Disabling cloud startup scripts'
    modules = glob( '%s/etc/init/cloud*.conf' % bind )
    for module in modules:
        path, ext = splitext( module )
        override = path + '.override'
        call( 'echo manual | sudo tee ' + override, shell=True )


def addMininetUser( nbd ):
    "Add mininet user/group to filesystem"
    print '* Adding mininet user to filesystem on device', nbd
    # 1. We bind-mount / into a temporary directory, and
    # then mount the volume's /etc and /home on top of it!
    mnt = mkdtemp()
    bind = mkdtemp()
    srun( 'mount %s %s' % ( nbd, mnt ) )
    srun( 'mount -B / ' + bind )
    srun( 'mount -B %s/etc %s/etc' % ( mnt, bind ) )
    srun( 'mount -B %s/home %s/home' % ( mnt, bind ) )
    def chroot( cmd ):
        "Chroot into bind mount and run command"
        call( 'sudo chroot %s ' % bind + cmd, shell=True )
    # 1a. Add hostname entry in /etc/hosts
    addTo( bind + '/etc/hosts', '127.0.1.1 mininet-vm' )
    # 2. Next, we delete any old mininet user and add a new one
    chroot( 'deluser mininet' )
    chroot( 'useradd --create-home mininet' )
    print '* Setting password'
    call( 'echo mininet:mininet | sudo chroot %s chpasswd -c SHA512'
          % bind, shell=True )
    # 2a. Add mininet to sudoers
    addTo( bind + '/etc/sudoers', 'mininet ALL=NOPASSWD: ALL' )
    # 2b. Disable cloud junk
    disableCloud( bind )
    chroot( 'sudo update-rc.d landscape-client disable' )
    # 2c. Add serial getty
    print '* Adding getty on ttyS0'
    chroot( 'cp /etc/init/tty1.conf /etc/init/ttyS0.conf' )
    chroot( 'sed -i "s/tty1/ttyS0/g" /etc/init/ttyS0.conf' )
    # 3. Lastly, we umount and clean up everything
    run( 'sync' )
    srun( 'umount %s/home ' % bind )
    srun( 'umount %s/etc ' % bind )
    srun( 'umount %s' % bind )
    srun( 'umount ' + mnt )
    run( 'rmdir ' + bind )
    run( 'rmdir ' + mnt )
    # 4. Just to make sure, we check the filesystem
    srun( 'e2fsck -y ' + nbd )


def attachNBD( cow, flags='' ):
    """Attempt to attach a COW disk image and return its nbd device
       flags: additional flags for qemu-nbd (e.g. -r for readonly)"""
    # qemu-nbd requires an absolute path
    cow = abspath( cow )
    print '* Checking for unused /dev/nbdX device ',
    for i in range ( 0, 63 ):
        nbd = '/dev/nbd%d' % i
        print i,
        # Check whether someone's already messing with that device
        if call( [ 'pgrep', '-f', nbd ] ) == 0:
            continue
        # Fails without -v for some annoying reason...
        print
        srun( 'qemu-nbd %s -c %s %s' % ( flags, nbd, cow ) )
        return nbd
    raise Exception( "Error: could not find unused /dev/nbdX device" )


def detachNBD( nbd ):
    "Detatch an nbd device"
    srun( 'qemu-nbd -d ' + nbd )


def makeCOWDisk( image, dir='.' ):
    "Create new COW disk for image"
    disk, kernel = fetchImage( image )
    cow = '%s/%s.qcow2' % ( dir, image )
    print '* Creating COW disk', cow
    run( 'qemu-img create -f qcow2 -b %s %s' % ( disk, cow ) )
    print '* Resizing COW disk and file system'
    run( 'qemu-img resize %s +8G' % cow )
    srun( 'modprobe nbd max-part=64')
    nbd = attachNBD( cow )
    srun( 'e2fsck -y ' + nbd )
    srun( 'resize2fs ' + nbd )
    addMininetUser( nbd )
    detachNBD( nbd )
    return cow, kernel


def makeVolume( volume, cylinders=1000  ):
    """Create volume as a qcow2 and add a single boot partition
       cylinders: number of ~8MB (255*63*512) cylinders in volume"""
    heads, sectors, bytes = 255, 63, 512
    size = cylinders * heads * sectors * bytes
    print '* Creating volume of size', size
    run( 'qemu-img create -f qcow2 %s %s' % ( volume, size ) )
    print '* Partitioning volume'
    # We need to mount it using qemu-nbd!!
    nbd = attachNBD( volume )
    # A bit hacky - we may change this to use parted(8) later
    fdisk = Popen( [ 'sudo', 'fdisk', nbd ], stdin=PIPE )
    cmds = 'x\nc\n%d\nr\no\nn\np\n1\n\n\na\n1\nw\n' % cylinders
    fdisk.stdin.write( cmds )
    fdisk.wait()
    print '* Volume partition table:'
    print srun( 'fdisk -l ' + nbd )
    detachNBD( nbd )


def initPartition( partition, volume ):
    """Copy partition to volume-p1 and call addMininetUser"""
    srcdev = attachNBD( partition, flags='-r' )
    voldev = attachNBD( volume )
    print srun( 'fdisk -l ' + voldev )
    print srun( 'partx ' + voldev )
    dstdev = voldev + 'p1'
    print "* Copying partition from", srcdev, "to", dstdev
    print srun( 'time dd if=%s of=%s bs=1M' % ( srcdev, dstdev ) )
    print '* Resizing and adding Mininet user'
    srun( 'resize2fs ' + dstdev )
    srun( 'e2fsck -y ' + dstdev )
    addMininetUser( dstdev )
    detachNBD( voldev )
    detachNBD( srcdev )


def boot( cow, kernel, tap ):
    """Boot qemu/kvm with a COW disk and local/user data store
       cow: COW disk path
       kernel: kernel path
       tap: tap device to connect to VM
       returns: pexpect object to qemu process"""
    # pexpect might not be installed until after depend() is called
    global pexpect
    import pexpect
    if 'amd64' in kernel:
        kvm = 'qemu-system-x86_64'
    elif 'i386' in kernel:
        kvm = 'qemu-system-i386'
    else:
        print "Error: can't discern CPU for image", cow
        exit( 1 )
    cmd = [ 'sudo', kvm,
            '-machine accel=kvm',
            '-nographic',
            '-netdev user,id=mnbuild',
            '-device virtio-net,netdev=mnbuild',
            '-m 1024',
            '-k en-us',
            '-kernel', kernel,
            '-drive file=%s,if=virtio' % cow,
            '-append "root=/dev/vda1 init=/sbin/init console=ttyS0" ' ]
    cmd = ' '.join( cmd )
    print '* STARTING VM'
    print cmd
    vm = pexpect.spawn( cmd, timeout=TIMEOUT )
    return vm


def interact( vm ):
    "Interact with vm, which is a pexpect object"
    prompt = '\$ '
    print '* Waiting for login prompt'
    vm.expect( 'login: ' )
    print '* Logging in'
    vm.sendline( 'mininet' )
    print '* Waiting for password prompt'
    vm.expect( 'Password: ' )
    print '* Sending password'
    vm.sendline( 'mininet' )
    print '* Waiting for login...'
    vm.expect( prompt )
    print '* Sending hostname command'
    vm.sendline( 'hostname' )
    print '* Waiting for output'
    vm.expect( prompt )
    print '* Fetching Mininet VM install script'
    vm.sendline( 'wget '
                 'https://raw.github.com/mininet/mininet/master/util/vm/'
                 'install-mininet-vm.sh' )
    vm.expect( prompt )
    print '* Running VM install script'
    vm.sendline( 'bash install-mininet-vm.sh' )
    print '* Waiting for script to complete... '
    # Gigantic timeout for now ;-(
    vm.expect( 'Done preparing Mininet', timeout=3600 )
    print '* Completed successfully'
    vm.expect( prompt )
    print '* Testing Mininet'
    vm.sendline( 'sudo mn --test pingall' )
    if vm.expect( [ ' 0% dropped', pexpect.TIMEOUT ], timeout=45 ):
        print '* Sanity check succeeded'
    else:
        print '* Sanity check FAILED'
    vm.expect( prompt )
    print '* Making sure cgroups are mounted'
    vm.sendline( 'sudo service cgroup-lite restart' )
    vm.expect( prompt )
    vm.sendline( 'sudo cgroups-mount' )
    vm.expect( prompt )
    print '* Running make test'
    vm.sendline( 'cd ~/mininet; sudo make test' )
    vm.expect( prompt )
    print '* Shutting down'
    vm.sendline( 'sync; sudo shutdown -h now' )
    print '* Waiting for EOF/shutdown'
    vm.read()
    print '* Interaction complete'


def cleanup():
    "Clean up leftover qemu-nbd processes and other junk"
    call( 'sudo pkill -9 qemu-nbd', shell=True )


def convert( cow, basename ):
    """Convert a qcow2 disk to a vmdk and put it a new directory
       basename: base name for output vmdk file"""
    vmdk = basename + '.vmdk'
    print '* Converting qcow2 to vmdk'
    run( 'qemu-img convert -f qcow2 -O vmdk %s %s' % ( cow, vmdk ) )
    return vmdk


def build( flavor='raring32server' ):
    "Build a Mininet VM"
    start = time()
    dir = mkdtemp( prefix=flavor + '-result-', dir='.' )
    os.chdir( dir )
    print '* Created working directory', dir
    image, kernel = fetchImage( flavor )
    volume = flavor + '.qcow2'
    makeVolume( volume )
    initPartition( image, volume )
    print '* VM image for', flavor, 'created as', volume
    logfile = open( flavor + '.log', 'w+' )
    print '* Logging results to', abspath( logfile.name )
    vm = boot( volume, kernel, logfile )
    vm.logfile_read = logfile
    interact( vm )
    vmdk = convert( volume, basename=flavor )
    print '* Converted VM image stored as', vmdk
    end = time()
    elapsed = end - start
    print '* Results logged to', abspath( logfile.name )
    print '* Completed in %.2f seconds' % elapsed
    print '* %s VM build DONE!!!!! :D' % flavor
    print
    os.chdir( '..' )


def parseArgs():
    "Parse command line arguments and run"
    parser = argparse.ArgumentParser( description='Mininet VM build script' )
    parser.add_argument( '--depend', action='store_true',
                         help='Install dependencies for this script' )
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
        print 'valid build flavors:', ' '.join( ImageURLBase )
    if args.clean:
        cleanup()
    flavors = args.flavor[ 1: ]
    for flavor in flavors:
        if flavor not in ImageURLBase:
            parser.print_help()
        # try:
        build( flavor )
        # except Exception as e:
        # print '* BUILD FAILED with exception: ', e
        # exit( 1 )
    if not ( args.depend or args.list or args.clean or flavors ):
        parser.print_help()

if __name__ == '__main__':
    parseArgs()
