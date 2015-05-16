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
           "  -a pid: attach to pid's specified namespaces\n"
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


int attach(int pid, int flags) {

    char path[PATH_MAX];
    int netns = -1;
    int pidns = -1;
    int mountns = -1;

    if (flags & CLONE_NEWNET) {
        /* Attach to pid's network namespace */
        sprintf(path, "/proc/%d/ns/net", pid);
        netns = open(path, O_RDONLY);
        if (netns < 0) {
            perror(path);
            return 1;
        }
        if (setns(netns, 0) != 0) {
            perror("setns");
            return 1;
        }
    }

    if (flags & CLONE_NEWPID) {
        /* Attach to pid namespace */
        sprintf(path, "/proc/%d/ns/pid", pid);
        pidns = open(path, O_RDONLY);
        if (pidns < 0) {
            perror(path);
            return 1;
        }
        if (setns(pidns, 0) != 0) {
            perror("pidns setns");
            return 1;
        }
    }

    if (flags & CLONE_NEWNS) {
        char *cwd = get_current_dir_name();
        /* Plan A: call setns() to attach to mount namespace */
        sprintf(path, "/proc/%d/ns/mnt", pid);
        mountns = open(path, O_RDONLY);
        if (mountns < 0 || setns(mountns, 0) != 0) {
            /* Plan B: chroot into pid's root file system */
            sprintf(path, "/proc/%d/root", pid);
            if (chroot(path) < 0) {
                perror(path);
                return 1;
            }
        }
        /* chdir to correct working directory */
        if (chdir(cwd) != 0) {
            perror(cwd);
            return 1;
        }
    }

    return 0;
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

    while ((c = getopt(argc, argv, "+cdmnPpa:g:r:uvh")) != -1)
        switch(c) {
            case 'c': closefds = 1; break;
            case 'd':   detachtty = 1; break;
            case 'm':   flags |= CLONE_NEWNS; break;
            case 'n':   flags |= CLONE_NEWNET; break;
            case 'p':   printpid = 1; break;
            case 'P':   flags |= CLONE_NEWPID; break;
            case 'a':   attachpid = atoi(optarg); break;
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
      attach(attachpid, flags);
    }
    else {
        /* Create new namespace(s) */
        if (unshare(flags) == -1) {
            perror("unshare");
            return 1;
        }
    }

    if (flags & CLONE_NEWPID) {
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
                printf("\001%d\n", pid);
                fflush(stdout);
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
