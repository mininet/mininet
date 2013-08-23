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

More notes:
    
- We use Ubuntu's cloud images, which means that we need to 
  adapt them for our own (evil) purposes. This isn't ideal
  but is the easiest way to get official Ubuntu images until
  they start building official non-cloud images.

- We could install grub into a raw ext4 partition rather than
  partitioning everything. This would save time and it might
  also confuse people who might be expecting a "normal" volume
  and who might want to expand it and add more partitions.
  On the other hand it makes the file system a lot easier to mount
  and modify!! But vmware might not be able to boot it.

- grub-install fails miserably unless you load part_msdos !!

- Installing TexLive is just painful - I would like to avoid it
  if we could... wireshark plugin build is also slow and painful...

- Maybe we want to install our own packages for these things...
  that would make the whole installation process a lot easier,
  but it would mean that we don't automatically get upstream
  updates

"""

import os
from os import stat
from stat import ST_MODE
from os.path import exists, splitext, abspath
from sys import exit, argv
from glob import glob
from urllib import urlretrieve
from subprocess import check_output, call, Popen, PIPE
from tempfile import mkdtemp
from time import time, strftime, localtime
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
    "Install packagedependencies"
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
    if exists( disk ):
        log( '* Found', disk )
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
            log( '* Retrieving', url )
            urlretrieve( url, tgz )
        log( '* Extracting', tgz )
        run( 'tar -C %s -xzf %s' % ( dir, tgz ) )
        # Write-protect disk image so it remains pristine;
        # We will not use it directly but will use a COW disk
        log( '* Write-protecting disk image', disk )
        os.chmod( disk, 0444 )
    return disk, kernel


def addTo( file, line ):
    "Add line to file if it's not there already"
    if call( [ 'sudo', 'grep', line, file ] ) != 0:
        call( 'echo "%s" | sudo tee -a %s > /dev/null' % ( line, file ),
              shell=True )


def disableCloud( bind ):
    "Disable cloud junk for disk mounted at bind"
    log( '* Disabling cloud startup scripts' )
    modules = glob( '%s/etc/init/cloud*.conf' % bind )
    for module in modules:
        path, ext = splitext( module )
        call( 'echo manual | sudo tee %s.override > /dev/null' % path,
              shell=True )


def addMininetUser( nbd ):
    "Add mininet user/group to filesystem"
    log( '* Adding mininet user to filesystem on device', nbd )
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
    chroot( 'useradd --create-home --shell /bin/bash mininet' )
    log( '* Setting password' )
    call( 'echo mininet:mininet | sudo chroot %s chpasswd -c SHA512'
          % bind, shell=True )
    # 2a. Add mininet to sudoers
    addTo( bind + '/etc/sudoers', 'mininet ALL=NOPASSWD: ALL' )
    # 2b. Disable cloud junk
    disableCloud( bind )
    chroot( 'sudo update-rc.d landscape-client disable' )
    # 2c. Add serial getty
    log( '* Adding getty on ttyS0' )
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


def makeCOWDisk( image, dir='.' ):
    "Create new COW disk for image"
    disk, kernel = fetchImage( image )
    cow = '%s/%s.qcow2' % ( dir, image )
    log( '* Creating COW disk', cow )
    run( 'qemu-img create -f qcow2 -b %s %s' % ( disk, cow ) )
    log( '* Resizing COW disk and file system' )
    run( 'qemu-img resize %s +8G' % cow )
    nbd = attachNBD( cow )
    srun( 'e2fsck -y ' + nbd )
    srun( 'resize2fs ' + nbd )
    addMininetUser( nbd )
    detachNBD( nbd )
    return cow, kernel


def makeVolume( volume, size='8G'  ):
    """Create volume as a qcow2 and add a single boot partition"""
    log( '* Creating volume of size', size )
    run( 'qemu-img create -f qcow2 %s %s' % ( volume, size ) )
    log( '* Partitioning volume' )
    # We need to mount it using qemu-nbd!!
    nbd = attachNBD( volume )
    parted = Popen( [ 'sudo', 'parted', nbd ], stdin=PIPE )
    cmds = [ 'mklabel msdos',
             'mkpart primary ext4 1 %s' % size,
             'set 1 boot on',
             'quit' ]
    parted.stdin.write( '\n'.join( cmds ) + '\n' )
    parted.wait()
    log( '* Volume partition table:' )
    log( srun( 'fdisk -l ' + nbd ) )
    detachNBD( nbd )


def installGrub( voldev, partnum=1 ):
    "Install grub2 on voldev to boot from partition partnum"
    mnt = mkdtemp()
    # Find partitions and make sure we have partition 1
    assert ( '# %d:' % partnum ) in srun( 'partx ' + voldev )
    partdev = voldev + 'p%d' % partnum
    srun( 'mount %s %s' % ( partdev, mnt ) )
    # Make sure we have a boot directory
    bootdir = mnt + '/boot'
    run( 'ls ' + bootdir )
    # Install grub - make sure we preload part_msdos !!
    srun( 'grub-install --boot-directory=%s --modules=part_msdos %s' % (
          bootdir, voldev ) )
    srun( 'umount ' + mnt )
    run( 'rmdir ' + mnt )


def initPartition( partition, volume ):
    """Copy partition to volume-p1 and initialize everything"""
    srcdev = attachNBD( partition, flags='-r' )
    voldev = attachNBD( volume )
    log( srun( 'fdisk -l ' + voldev ) )
    log( srun( 'partx ' + voldev ) )
    dstdev = voldev + 'p1'
    log( "* Copying partition from", srcdev, "to", dstdev )
    log( srun( 'dd if=%s of=%s bs=1M' % ( srcdev, dstdev ) ) )
    log( '* Resizing file system' )
    srun( 'resize2fs ' + dstdev )
    srun( 'e2fsck -y ' + dstdev )
    log( '* Adding mininet user' )
    addMininetUser( dstdev )
    log( '* Installing grub2' )
    installGrub( voldev, partnum=1 )
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
        log( "Error: can't discern CPU for image", cow )
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
    log( '* STARTING VM' )
    log( cmd )
    vm = pexpect.spawn( cmd, timeout=TIMEOUT )
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
    log( '* Waiting for script to complete... ' )
    # Gigantic timeout for now ;-(
    vm.expect( 'Done preparing Mininet', timeout=3600 )
    log( '* Completed successfully' )
    vm.expect( prompt )
    log( '* Testing Mininet' )
    vm.sendline( 'sudo mn --test pingall' )
    if vm.expect( [ ' 0% dropped', pexpect.TIMEOUT ], timeout=45 ) == 0:
        log( '* Sanity check succeeded' )
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


def build( flavor='raring32server' ):
    "Build a Mininet VM"
    start = time()
    dir = mkdtemp( prefix=flavor + '-result-', dir='.' )
    os.chdir( dir )
    log( '* Created working directory', dir )
    image, kernel = fetchImage( flavor )
    volume = flavor + '.qcow2'
    makeVolume( volume )
    initPartition( image, volume )
    log( '* VM image for', flavor, 'created as', volume )
    logfile = open( flavor + '.log', 'w+' )
    log( '* Logging results to', abspath( logfile.name ) )
    vm = boot( volume, kernel, logfile )
    vm.logfile_read = logfile
    interact( vm )
    vmdk = convert( volume, basename=flavor )
    log( '* Converted VM image stored as', vmdk )
    end = time()
    elapsed = end - start
    log( '* Results logged to', abspath( logfile.name ) )
    log( '* Completed in %.2f seconds' % elapsed )
    log( '* %s VM build DONE!!!!! :D' % flavor )
    log( '* ' )
    os.chdir( '..' )


def listFlavors():
    "List valid build flavors"
    print '\nvalid build flavors:', ' '.join( ImageURLBase ), '\n'

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
        listFlavors()
    if args.clean:
        cleanup()
    flavors = args.flavor[ 1: ]
    for flavor in flavors:
        if flavor not in ImageURLBase:
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

if __name__ == '__main__':
    parseArgs()
