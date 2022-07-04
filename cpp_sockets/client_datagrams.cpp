// Client side implementation of UDP client-server model
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <string.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <arpa/inet.h>
#include <netinet/in.h>
	
#define PORT 20001
#define BUF_SIZE 256
	
// Driver code
int main() {
	int sockfd;
	char buffer[BUF_SIZE];
	char *msg = "To be or not to be, that is a question.\n";
	struct sockaddr_in servaddr;
	
	// Creating socket file descriptor
	if ( (sockfd = socket(AF_INET, SOCK_DGRAM, 0)) < 0 ) {
		perror("socket creation failed");
		exit(EXIT_FAILURE);
	}
	
	memset(&servaddr, 0, sizeof(servaddr));
		
	// Filling server information
	servaddr.sin_family = AF_INET;
	servaddr.sin_port = htons(PORT);
	servaddr.sin_addr.s_addr = INADDR_ANY;
		
	int n;
    unsigned int len;
    
	sendto(sockfd, (const char *)msg, strlen(msg),
		MSG_CONFIRM, (const struct sockaddr *) &servaddr,
			sizeof(servaddr));
	printf("Message sent.\n");
			
	n = recvfrom(sockfd, (char *)buffer, BUF_SIZE,
				MSG_WAITALL, (struct sockaddr *) &servaddr,
				&len);
	buffer[n] = '\0';
	printf("Server response: %s\n", buffer);
	
	close(sockfd);
	return 0;
}
