/* udpbwtest: a simple bandwidth test
 * 
 * To test all-to-all communication, we simply open up a
 * UDP socket and repeat the following:
 *
 * 1. Send a packet to a random host if possible
 * 2. Receive a packet if possible
 * 3. Periodically report our I/O bandwidth
 *
 */
 
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <strings.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <assert.h>
#include <sys/time.h>
#include <poll.h>
#include <signal.h>

enum { Port=12345 };

/* Handy utility functions */

int bindAddr( int fd, long addr, u_short port ) {
   /* Easy interface to bind */
   struct sockaddr_in sa;
   bzero( &sa, sizeof( sa ) );
   sa.sin_family = AF_INET;
   sa.sin_addr.s_addr = htonl( addr );
   sa.sin_port = htons( port );
   return bind( fd, ( struct sockaddr * )&sa, sizeof( sa ) );   
}

int udpSocket( u_short port ) {
   /* Easy interface to making a UDP socket */
   int fd = socket( AF_INET, SOCK_DGRAM, 0 );
   if ( fd < 0 ) { return fd; }
   int err = bindAddr( fd, INADDR_ANY, port );
   if ( err < 0 ) { return err; }
   return fd;
}

ssize_t sendBytes( int sock, char *outbuf, size_t bufsize, 
   struct in_addr *addr, u_short port ) {
   /* Simpler sendto */
   struct sockaddr_in sa;
   int err;
   bzero( &sa, sizeof( sa ) );
   sa.sin_family = AF_INET;
   sa.sin_addr = *addr;
   sa.sin_port = htons( port );
   err = sendto( sock, outbuf, bufsize, 0, (const struct sockaddr *) &sa,
      sizeof( sa ) );
   if ( err < 0 ) { perror( "sendto:" ); }
   return err;
}

ssize_t recvBytes( int sock, char *inbuf, size_t bufsize, 
   struct in_addr *addr) {
   /* Simpler recvfrom */
   struct sockaddr_in sa;
   socklen_t saLen = sizeof( sa );
   ssize_t len;
   len = recvfrom( sock, inbuf, bufsize, 0, (struct sockaddr *) &sa, &saLen );
   if ( len >= 0 ) {
      assert( saLen == sizeof( sa ) );
      *addr = sa.sin_addr;
   }
   else { perror( "recvfrom:" ); }
   return len;
}


int readable( int fd ) {
   /* Poll a single file descriptor for reading */
   struct pollfd fds = { fd, POLLIN, POLLIN };
   int result = poll( &fds, 1, 0 );
   /* True if there is one readable descriptor */
   return ( result == 1 );
}

int writable( int fd ) {
   /* Poll a single file descriptor for writing */
   struct pollfd fds = { fd, POLLOUT, POLLOUT };
   int result = poll( &fds, 1, 0 );
   /* True if there is one writable descriptor */
   return ( result == 1 );
}

int poll1( int fd, int flags, int ms ) {
   /* Call poll on a single descriptor */
   struct pollfd fds[] = { { fd, flags, 0 } };
   return poll( fds, 1, ms );   
}

int waitReadable( int fd, int ms ) { return poll1( fd, POLLIN, ms ); }
int waitWritable( int fd, int ms ) { return poll1( fd, POLLIN, ms ); }
int waitReadableOrWritable( int fd, int ms ) {
    return poll1( fd, POLLIN | POLLOUT, ms  );
}

/* Timer support */

int alarm = 0; 
void handleAlarm( int sig) { alarm = 1; }

void startTimer( int seconds) {
   struct itimerval v;
   v.it_interval.tv_sec = seconds;
   v.it_interval.tv_usec = 0;
   v.it_value = v.it_interval;
   signal( SIGALRM, handleAlarm );
   setitimer( ITIMER_REAL, &v, 0 );
}

void startOneSecondTimer() { startTimer( 1 ); }

void stopTimer() { 
   struct itimerval v;
   bzero( &v, sizeof v );
   setitimer( ITIMER_REAL, &v, 0 );
}

/* Actual program */

void bwtest( int sock, struct in_addr *hosts, int hostCount ) {
   
   /* Test our bandwidth, by receiving whatever we get, and sending
    * randomly to a set of hosts */
   
   char outbuf[ 1024 ];
   char inbuf[ 1024 ];
   time_t seconds = time( 0 );
   uint64_t b, bytes;
   uint64_t inbytes = 0, outbytes = 0;
   int i;
   
   for ( i = 0; i < sizeof( outbuf ); i++ ) { outbuf[ i ] = i % 255; }
   
   while ( 1 ) {
      size_t addr_len;
      struct in_addr addr = hosts[ random() % hostCount ];
      /* Wait until we have something to do. */
      waitReadableOrWritable( sock, 0 );
      /* Receive some bytes */
      for ( b = 0; b < 10 && readable( sock ); b += 1 ) {
         bytes = recvBytes( sock, inbuf, sizeof( inbuf ), &addr );
         inbytes += bytes;
      }
      /* Send some bytes */
      for ( b = 0; b < 10 && writable(sock); b += 1 ) {
         bytes = sendBytes( sock, outbuf, sizeof( outbuf ), 
            &addr, Port );
         outbytes += bytes;
      }
      /* Periodically report bandwidth */
      if ( alarm ) {
         alarm = 0;
         seconds++;
         printf("%d s: in %.2f Mbps, out %.2f Mbps\n", 
            seconds, 8.0*inbytes/1e6, 8.0*outbytes/1e6 ); fflush( stdout );
         inbytes = outbytes = 0;
      }
   }
}

int main( int argc, char *argv[] ) {

   struct in_addr start, *hosts, addr;
   int count, sock, i;
   
   if ( argc < 2  ) {
      fprintf( stderr, "usage: %s host...\n", argv[ 0 ] );
      exit( 1 );
   }

   count = argc - 1;
   hosts = (struct in_addr *) malloc( count * sizeof( struct in_addr ) );
   if ( hosts == NULL ) { perror( "malloc:" ); exit( 1 ); }
   
   for ( i = 0; i < count; i++ ) 
      inet_aton( argv[ i + 1 ], &hosts[ i ] );
   
   sock = udpSocket( Port );
   if ( sock <  0 ) { perror( "udpSocket:" ); exit( 1 ); }
  
   startOneSecondTimer();

   bwtest( sock, hosts, count ); /* Never returns for now... */

   stopTimer();
   
}



