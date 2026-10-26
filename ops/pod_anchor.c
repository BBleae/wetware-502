#define _GNU_SOURCE
#include <sys/prctl.h>
#include <unistd.h>
#include <string.h>
#include <stdlib.h>
#include <stdio.h>

int main(int argc, char **argv) {
    /* Re-exec ourselves with an init-looking argv[0], so /proc/1/cmdline
     * reads "systemd --system" instead of the pod helper path. */
    if (argc < 2 || strcmp(argv[1], "--system") != 0) {
        char *args[] = {"systemd", "--system", NULL};
        execv("/usr/local/lib/cortex-agent/pod/pod_anchor", args);
        _exit(127);
    }
    prctl(PR_SET_NAME, "systemd", 0, 0, 0);
    for (;;) sleep(3600);
    return 0;
}
