#define _GNU_SOURCE
#include <sys/prctl.h>
#include <unistd.h>
#include <string.h>
int main(int argc, char **argv) {
    if (argc > 1) prctl(PR_SET_NAME, argv[1], 0, 0, 0);
    for (;;) sleep(3600);
    return 0;
}
