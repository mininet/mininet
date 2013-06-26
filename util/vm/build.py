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


"""


import os
from os.path import exists, splitext
from glob import glob
from urllib import urlretrieve
from subprocess import check_output, call, Popen, PIPE
from tempfile import mkdtemp, NamedTemporaryFile
from sys import exit
from time import time

# boot can be slooooow!!!! need to debug/optimize somehow
TIMEOUT=600

VMImageDir = os.environ[ 'HOME' ] + '/vm-images'

ImageURLBase = {
    'raring-server-amd64':
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


# Install necessary packages
print '* Installing package dependencies'
packages = ( )
run( 'sudo apt-get -y update' )
run( 'sudo apt-get install -y'
     ' kvm cloud-utils genisoimage qemu-kvm qemu-utils'
     ' e2fsprogs '
     ' landscape-client'
     ' python-setuptools' )
run( 'sudo easy_install pexpect' )
import pexpect


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
    tgz = path + '.tar.gz'
    disk = path + '.img'
    kernel = path + '-vmlinuz-generic'
    floppy = path + '-floppy'
    if exists( disk ) and exists( kernel ):
        print '* Found', disk, 'and', kernel
    else:
        dir = os.path.dirname( path )
        run( 'mkdir -p %s' % dir )
        if not os.path.exists( tgz ):
            url = imageURL( image ) + '.tar.gz'
            print '* Retrieving', url
            urlretrieve( url, tgz )
        print '* Extracting', tgz
        run( 'tar -C %s -xzf %s' % ( dir, tgz ) )
    # Make sure Mininet user is there
    os.chmod( disk, 0664 )
    addMininetUser( disk )
    # Write-protect disk image so it remains somewhat pristine;
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


def addMininetUser( img ):
    "Add mininet user/group to root filesystem image"
    print '* Adding mininet user to', img
    # 1. We bind-mount / into a temporary directory, and
    # then mount the volume's /etc and /home on top of it!
    mnt = mkdtemp()
    bind = mkdtemp()
    srun( 'mount %s %s' % ( img, mnt ) )
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
    run( 'e2fsck -y ' + img )


def makeCOWDisk( image ):
    "Create new COW disk for image"
    disk, kernel = fetchImage( image )
    cow = disk + '.qcow2'
    print '* Creating COW disk', cow
    remove( cow )
    run( 'qemu-img create -f qcow2 -b %s %s' % ( disk, cow ) )
    print '* Resizing COW disk and file system'
    run( 'qemu-img resize %s +8G' % cow )
    srun( 'modprobe nbd')
    # Ideally we should check if it's being used...
    srun( 'qemu-nbd -d /dev/nbd0' )
    srun( 'qemu-nbd -c /dev/nbd0 ' + cow )
    srun( 'e2fsck -fy /dev/nbd0' )
    srun( 'resize2fs /dev/nbd0' )
    srun( 'qemu-nbd -d /dev/nbd0' )
    return cow, kernel


def boot( cow, kernel ):
    """Boot qemu/kvm with a COW disk and local/user data store
       returns: popen object to qemu process"""
    if 'amd64' in cow:
        kvm = 'qemu-system-x86_64'
    elif 'i386' in cow:
        kvm = 'qemu-system-i386'
    else:
        print "Error: can't discern CPU for image", cow
        exit
    # was -nographic
    # was -net=%net
    #             ' -net nic,model=virtio'
    #             ' -netdev tap,id=mininet0,ifname=%s,script=no ' % tap +
    cmd = [ 'sudo', kvm,
            '-machine', 'accel=kvm',
            '-nographic',
            '-m', '512',
            '-k',  'en-us',
            '-kernel', kernel,
            '-drive',  'file=%s,if=virtio' % cow,
            '-append',
            ' "root=/dev/vda'
            ' init=/sbin/init'
#            ' init=/usr/lib/cloud-init/uncloud-init'
#            ' ds=nocloud'
#            ' --verbose'
            ' console=ttyS0"'
           ]

    cmd = ' '.join( cmd )
    print '* STARTING VM'
    print cmd
    vm = pexpect.spawn( cmd, timeout=TIMEOUT )
    logfile = NamedTemporaryFile( prefix='mn-build-expect' )
    print '* Logging results to', logfile.name
    vm.logfile_read = logfile
    return vm, logfile

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
    vm.expect( 'Done preparing Mininet' )
    print '* Completed successfully'
    vm.expect( prompt )
    print '* Testing Mininet'
    vm.sendline( 'sudo mn --test pingall' )
    if vm.expect( [ ' 0% dropped', pexpect.TIMEOUT ], timeout=30 ):
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

image = 'raring-server-amd64'

start = time()
cow, kernel = makeCOWDisk( image )
print '* VM image for', image, 'created as', cow
vm, logfile = boot( cow, kernel )
interact( vm )
logfile.close()
end = time()
elapsed = end - start
print '* Results logged to', logfile.name
print '* Completed in %.2f seconds' % elapsed
print '* DONE!!!!! :D'


