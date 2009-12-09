/* netns: run a command in a network namespace.
 * Simplified from netunshare.c on lxc.sf.net
*/

#include <stdio.h>
#include <sched.h>
#include <unistd.h>

int main(int argc, char *argv[])
{	
	if (unshare(CLONE_NEWNET) == -1) {
		perror("unshare");
		return 1;
	} 
	
	if (argc) {
		execve(argv[1], &argv[1], __environ);
		perror("execve");
		return 1;
	}

	return 0;
}

