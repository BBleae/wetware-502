#define _GNU_SOURCE
#include <sys/prctl.h>
#include <sys/wait.h>
#include <unistd.h>
#include <signal.h>

/* Minimal PID 1 for the namespace: reap orphans and keep the namespace up.
 * The argv[0] is set to "systemd --system" by the launcher. */
int main(void) {
    prctl(PR_SET_NAME, "systemd", 0, 0, 0);
    prctl(PR_SET_CHILD_SUBREAPER, 1, 0, 0, 0);
    signal(SIGCHLD, SIG_DFL);
    for (;;) {
        while (waitpid(-1, NULL, WNOHANG) > 0) { }
        sleep(1);
    }
    return 0;
}
