obj-m = sch_htb.o
KVERSION = $(shell uname -r)
all:
	        make -C /lib/modules/$(KVERSION)/build M=$(PWD) modules
install:
		test -e /lib/modules/$(KVERSION)/kernel/net/sched/sch_htb.ko.bak || mv /lib/modules/$(KVERSION)/kernel/net/sched/sch_htb.ko /lib/modules/$(KVERSION)/kernel/net/sched/sch_htb.ko.bak
		cp sch_htb.ko /lib/modules/$(KVERSION)/kernel/net/sched/sch_htb.ko
		rmmod sch_htb
		modprobe sch_htb
clean:
	        make -C /lib/modules/$(KVERSION)/build M=$(PWD) clean
