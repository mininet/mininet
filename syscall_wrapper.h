#include <stdlib.h>
#include <stdio.h>

/*
 *	This wrapper will ease the invocation of newly added system calls
 *	Think of it as a part of glibc
 */

int virtualtimeunshare(unsigned long, int);
int settimedilationfactor(int, int);

