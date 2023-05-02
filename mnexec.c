/* mnexec: execution utility for mininet
 *
 * Starts up programs and does things that are slow or
 * difficult in Python, including:
 *
 *  - closing all file descriptors except stdin/out/error
 *  - detaching from a controlling tty using setsid
 *  - running in network and mount namespaces
 *  - printing out the pid of a process so we can identify it later
 *  - attaching to a namespace and cgroup
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
#include <sys/types.h>
#include <sys/stat.h>
#include <dirent.h>

#if !defined(VERSION)
#define VERSION "(devel)"
#endif

void usage(char *name)
{
    printf("Execution utility for Mininet\n\n"
           "Usage: %s [-cdnp] [-a pid] [-g group] [-r rtprio] cmd args...\n\n"
           "Options:\n"
           "  -c: close all file descriptors except stdin/out/error\n"
           "  -d: detach from tty by calling setsid()\n"
           "  -n: run in new network and mount namespaces\n"
           "  -p: print ^A + pid\n"
           "  -a pid: attach to pid's network and mount namespaces\n"
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

int main(int argc, char *argv[])
{
    int c;
    int fd;
    DIR *dir;
    struct dirent *de;
    char path[PATH_MAX];
    int nsid;
    int pid;
    char *cwd = get_current_dir_name();
    static struct sched_param sp;

    while ((c = getopt(argc, argv, "+cdnpa:g:r:vh")) != -1)
        switch(c) {
        case 'c':
            /* close file descriptors except stdin/out/error */
            if ((dir = opendir("/proc/self/fd"))) {
                while ((de = readdir(dir)))
                    if ((fd = atoi(de->d_name)) > 2)
                        close(fd);
            }
            /* fall back to old method if needed */
            else for (fd = getdtablesize(); fd > 2; fd--)
                     close(fd);
            break;
        case 'd':
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
            break;
        case 'n':
            /* run in network and mount namespaces */
            if (unshare(CLONE_NEWNET|CLONE_NEWNS) == -1) {
                perror("unshare");
                return 1;
            }

            /* Mark our whole hierarchy recursively as private, so that our
             * mounts do not propagate to other processes.
             */

            if (mount("none", "/", NULL, MS_REC|MS_PRIVATE, NULL) == -1) {
                perror("remount");
                return 1;
            }

            /* mount sysfs to pick up the new network namespace */
            if (mount("sysfs", "/sys", "sysfs", MS_MGC_VAL, NULL) == -1) {
                perror("mount");
                return 1;
            }
            break;
        case 'p':
            /* print pid */
            printf("\001%d\n", getpid());
            fflush(stdout);
            break;
        case 'a':
            /* Attach to pid's network namespace and mount namespace */
            pid = atoi(optarg);
            sprintf(path, "/proc/%d/ns/net", pid);
            nsid = open(path, O_RDONLY);
            if (nsid < 0) {
                perror(path);
                return 1;
            }
            if (setns(nsid, 0) != 0) {
                perror("setns");
                return 1;
            }
            /* Plan A: call setns() to attach to mount namespace */
            sprintf(path, "/proc/%d/ns/mnt", pid);
            nsid = open(path, O_RDONLY);
            if (nsid < 0 || setns(nsid, 0) != 0) {
                /* Plan B: chroot/chdir into pid's root file system */
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
            break;
        case 'g':
            /* Attach to cgroup */
            cgroup(optarg);
            break;
        case 'r':
            /* Set RT scheduling priority */
            sp.sched_priority = atoi(optarg);
            if (sched_setscheduler(getpid(), SCHED_RR, &sp) < 0) {
                perror("sched_setscheduler");
                return 1;
            }
            break;
        case 'v':
            printf("%s\n", VERSION);
            exit(0);
        case 'h':
            usage(argv[0]);
            exit(0);
        default:
            usage(argv[0]);
            exit(1);
        }

    if (optind < argc) {
        execvp(argv[optind], &argv[optind]);
        perror(argv[optind]);
        return 1;
    }

    usage(argv[0]);

    return 0;
}
