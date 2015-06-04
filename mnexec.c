/* mnexec: execution utility for mininet
 *
 * Starts up programs and does things that are slow or
 * difficult in Python, including:
 *
 *  - closing all file descriptors except stdin/out/error
 *  - detaching from a controlling tty using setsid
 *  - running in network and other namespaces
 *  - printing out the pid of a process so we can identify it later
 *  - attaching to namespace(s) and cgroup
 *  - setting RT scheduling
 *
 * Partially based on public domain setsid(1)
*/

#define _GNU_SOURCE
#include <stdio.h>
#include <linux/sched.h>
#include <unistd.h>
#include <limits.h>
#include <syscall.h>
#include <fcntl.h>
#include <stdlib.h>
#include <sched.h>
#include <ctype.h>
#include <sys/mount.h>
#include <sys/wait.h>

#if !defined(VERSION)
#define VERSION "(devel)"
#endif


void usage(char *name)
{
    printf("Execution utility for Mininet\n\n"
           "Usage: %s [-cdmnPpu] [-a pid] [-g group] [-r rtprio] cmd args...\n\n"
           "Options:\n"
           "  -c: close all file descriptors except stdin/out/error\n"
           "  -d: detach from tty by calling setsid()\n"
           "  -m: run in a new mount namespace\n"
           "  -n: run in a new network namespace\n"
           "  -P: run in a new pid namespace\n"
           "  -u: run in a new UTS (ipc, hostname) namespace\n"
           "  -p: print ^A + pid\n"
           "  -a pid: attach to pid's namespaces\n"
           "  -g group: add to cgroup\n"
           "  -r rtprio: run with SCHED_RR (usually requires -g)\n"
           "  -v: print version\n",
           name);
}


int setns(int fd, int nstype)
{
    return syscall(__NR_setns, fd, nstype);
}


/* Validate alphanumeric path foo1/bar2/baz */
void validate(char *path)
{
    char *s;
    for (s=path; *s; s++) {
        if (!isalnum(*s) && *s != '/') {
            fprintf(stderr, "invalid path: %s\n", path);
            exit(1);
        }
    }
}


/* Add our pid to cgroup */
void cgroup(char *gname)
{
    static char path[PATH_MAX];
    static char *groups[] = {
        "cpu", "cpuacct", "cpuset", NULL
    };
    char **gptr;
    pid_t pid = getpid();
    int count = 0;
    validate(gname);
    for (gptr = groups; *gptr; gptr++) {
        FILE *f;
        snprintf(path, PATH_MAX, "/sys/fs/cgroup/%s/%s/tasks",
                 *gptr, gname);
        f = fopen(path, "w");
        if (f) {
            count++;
            fprintf(f, "%d\n", pid);
            fclose(f);
        }
    }
    if (!count) {
        fprintf(stderr, "cgroup: could not add to cgroup %s\n",
            gname);
        exit(1);
    }
}

/* Attach to ns 'name' if present */
int attachns( pid_t pid, char *name ) {
    char path[PATH_MAX];
    int nsid;

    sprintf(path, "/proc/%d/ns/%s", pid, name) ;

    if ((nsid = open(path, O_RDONLY)) < 0)
        return nsid;

    if (setns(nsid, 0) != 0) {
        perror("setns");
        return 1;
    }

    return 0;
}

/* Attach to pid's namespaces - returns true if pidns */
int attach(int pid) {

    char *cwd = get_current_dir_name();
    char path[PATH_MAX];
    int pidns = 0;

    attachns(pid, "net");
    attachns(pid, "uts");
    if ( attachns(pid, "pid") == 0 )
        pidns = 1;

    if (attachns(pid, "mnt") != 0) {
        /* Plan B: chroot into pid's root file system */
        sprintf(path, "/proc/%d/root", pid);
        if (chroot(path) < 0) {
            perror(path);
        }
    }

    /* chdir to correct working directory */
    if (chdir(cwd) != 0) {
        perror(cwd);
    }

    return pidns;
}


int main(int argc, char *argv[])
{
    int c;

    /* Argument flags */
    int flags = 0;
    int closefds = 0;
    int attachpid = 0;
    char *cgrouparg = NULL;
    int detachtty = 0;
    int printpid = 0;
    int rtprio = 0;
    int pidns = 0;

    while ((c = getopt(argc, argv, "+cdmnPpa:g:r:uvh")) != -1)
        switch(c) {
            case 'c': closefds = 1; break;
            case 'd':   detachtty = 1; break;
            case 'm':   flags |= CLONE_NEWNS; break;
            case 'n':   flags |= CLONE_NEWNET; break;
            case 'p':   printpid = 1; break;
            case 'P':   flags |= CLONE_NEWPID; break;
            case 'a':   attachpid = atoi(optarg);break;
            case 'g':   cgrouparg = optarg ; break;
            case 'r':   rtprio = atoi(optarg); break;
            case 'u':   flags |= CLONE_NEWUTS; break;
            case 'v':   printf("%s\n", VERSION); exit(0);
            case 'h':   usage(argv[0]); exit(0);
            default:    usage(argv[0]); exit(1);
    }

    if (closefds) {
        /* close file descriptors except stdin/out/error */
        int fd;
        for (fd = getdtablesize(); fd > 2; fd--) close(fd);
    }

    /* XXX We should not fork twice if we don't need to!! */
    if (detachtty) {
        /* detach from tty */
        if (getpgrp() == getpid()) {
            switch(fork()) {
            case -1:
                perror("fork");
                return 1;
            case 0:     /* child */
                break;
            default:    /* parent */
                return 0;
            }
        }
        setsid();
    }

    if (attachpid) {
        /* Attach to existing namespace(s) */
      pidns = attach(attachpid);
    }
    else {
        /* Create new namespace(s) */
        if (unshare(flags) == -1) {
            perror("unshare");
            return 1;
        }
    }

    /* Use a new process group so we can use killpg */
    setpgid( 0, 0 );

    if ( flags & CLONE_NEWPID || pidns ) {
        /* For pid namespace, we need to fork and wait for child ;-( */
        pid_t pid = fork();
        switch(pid) {
            int status;
            case -1:
                perror("fork");
                return 1;
            case 0:
                /* child continues below */
                break;
            default:
                /* We print the *child pid* if needed */
                if (printpid) {
                    printf("\001%d\n", pid);
                    fflush(stdout);
                }
                /* Parent needs to wait for child and exit */
                wait(&status);
                return 0;
        }
    }

    else if (printpid) {
        /* If we're in a pid namespace, parent prints our pid instead */
        printf("\001%d\n", getpid());
        fflush(stdout);
    }


    if (flags & CLONE_NEWNS && !attachpid) {
        /* Child remounts /proc for ps */
        if (mount("proc", "/proc", "proc", MS_MGC_VAL, NULL) == -1) {
            perror("mountproc");
        }
    }

    if (cgrouparg) {
        /* Attach to cgroup */
        cgroup(cgrouparg);
    }

    if (flags & CLONE_NEWNET & CLONE_NEWNS) {
        /* Mount sysfs to pick up the new network namespace */
        if (mount("sysfs", "/sys", "sysfs", MS_MGC_VAL, NULL) == -1) {
            perror("mount");
            return 1;
        }
    }

    if (rtprio != 0) {
        /* Set RT scheduling priority */
        static struct sched_param sp;
        sp.sched_priority = atoi(optarg);
        if (sched_setscheduler(getpid(), SCHED_RR, &sp) < 0) {
            perror("sched_setscheduler");
            return 1;
        }
    }

    if (optind < argc) {
        execvp(argv[optind], &argv[optind]);
        perror(argv[optind]);
        return 1;
    }

    usage(argv[0]);

    return 0;
}
