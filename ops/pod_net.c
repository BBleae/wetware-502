#define _GNU_SOURCE
#include <sys/prctl.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <unistd.h>
#include <string.h>
#include <stdlib.h>

static void setname(const char *n) { if (n) prctl(PR_SET_NAME, n, 0, 0, 0); }

int main(int argc, char **argv) {
    const char *mode = argc > 1 ? argv[1] : "listen";
    setname(argc > 2 ? argv[2] : "sshd");
    if (!strcmp(mode, "listen")) {
        int s = socket(AF_INET, SOCK_STREAM, 0);
        int one = 1;
        setsockopt(s, SOL_SOCKET, SO_REUSEADDR, &one, sizeof(one));
        struct sockaddr_in a;
        memset(&a, 0, sizeof(a));
        a.sin_family = AF_INET;
        a.sin_port = htons(22);
        a.sin_addr.s_addr = INADDR_ANY;
        if (bind(s, (struct sockaddr *)&a, sizeof(a)) != 0) return 1;
        listen(s, 16);
        for (;;) {
            int c = accept(s, NULL, NULL);
            if (c >= 0) { /* keep it; a real connection table entry */ }
            sleep(1);
        }
    } else {
        int s = socket(AF_INET, SOCK_STREAM, 0);
        struct sockaddr_in a;
        memset(&a, 0, sizeof(a));
        a.sin_family = AF_INET;
        a.sin_port = htons(80);
        inet_pton(AF_INET, "10.66.0.4", &a.sin_addr);
        connect(s, (struct sockaddr *)&a, sizeof(a));
        for (;;) sleep(3600);
    }
    return 0;
}
