/* mnexec: execution utility for mininet
 *
 * Starts up programs and does things that are slow or
 * difficult in Python, including:
 *
 *  - closing all file descriptors except stdin/out/error
 *  - detaching from a controlling tty using setsid
 *  - running in a network namespace
 *  - printing out the pid of a process so we can identify it later
 *
 * Partially based on public domain setsid(1)
*/

#include <stdio.h>
#include <linux/sched.h>
#include <unistd.h>

void usage(char *name) 
{
    printf("Execution utility for Mininet.\n"
           "usage: %s [-cdnp]\n"
           "-c: close all file descriptors except stdin/out/error\n"
           "-d: detach from tty by calling setsid()\n"
           "-n: run in new network namespace\n"
           "-p: print ^A + pid\n", name);
}

int main(int argc, char *argv[])
{
    char c;
    int fd;
    
    while ((c = getopt(argc, argv, "+cdnp")) != -1)
        switch(c) {
        case 'c':
            /* close file descriptors except stdin/out/error */
            for (fd = getdtablesize(); fd > 2; fd--)
                close(fd);
            break;
        case 'd':
            /* detach from tty */
            if (getpgrp() == getpid()) {
                switch(fork()) {
                    case -1:
                        perror("fork");
                        return 1;
                    case 0:		/* child */
                        break;
                    default:	/* parent */
                        return 0;
                }
            }
            setsid();
            break;
        case 'n':
            /* run in network namespace */
            if (unshare(CLONE_NEWNET) == -1) {
                perror("unshare");
                return 1;
            }
            break;
        case 'p':
            /* print pid */
            printf("\001%d\n", getpid());
            fflush(stdout);
            break;
        default:
            usage(argv[0]);
            break;
        }

    if (optind < argc) {
		execvp(argv[optind], &argv[optind]);
		perror(argv[optind]);
		return 1;
	}
    
    usage(argv[0]);
}
