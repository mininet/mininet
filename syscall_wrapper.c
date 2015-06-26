#include <sys/syscall.h>

/*
 * hard coded number from syscall_64.tbl
 * depend on kernel patch
 */
#define VIRTUALTIMEUNSHARE 318
#define SETTIMEDILATIONFACTOR 321

int virtualtimeunshare(unsigned long flags, int dilation)
{
    return syscall(VIRTUALTIMEUNSHARE, flags | 0x02000000, dilation);
}

/*
 *  ppid == 0 : change caller itself's dilation
 *  ppid !=0 :  change caller's parent's dilation
 */
int settimedilationfactor(int dilation, int ppid)
{
	return syscall(SETTIMEDILATIONFACTOR, dilation, ppid);
}

