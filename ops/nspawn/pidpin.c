/* pidpin: launch a program with a fixed PID.
 *
 * The story requires the inference worker to be PID 4040 (the metabolic tether
 * is bound to that pid in the fiction, and operators read /proc/4040).  A plain
 * ExecStartPre that writes ns_last_pid is racy: every other fork on the same
 * pid namespace can steal 4040.  This launcher retries until the child really
 * lands on the wanted pid.
 *
 * usage: pidpin <wanted-pid> <pidfile> <prog> [args...]
 */
#define _GNU_SOURCE
#include <errno.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/wait.h>
#include <unistd.h>

static int set_last_pid(long value)
{
    FILE *fp = fopen("/proc/sys/kernel/ns_last_pid", "w");
    if (!fp)
        return -1;
    fprintf(fp, "%ld", value - 1);
    fclose(fp);
    return 0;
}

int main(int argc, char **argv)
{
    long wanted;
    char *end = NULL;
    int attempt;

    if (argc < 4) {
        fprintf(stderr, "usage: %s <wanted-pid> <pidfile> <prog> [args...]\n",
                argv[0]);
        return 64;
    }
    wanted = strtol(argv[1], &end, 10);
    if (!end || *end || wanted < 2 || wanted > 4000000) {
        fprintf(stderr, "pidpin: bad pid %s\n", argv[1]);
        return 64;
    }

    for (attempt = 0; attempt < 4000; attempt++) {
        pid_t pid;

        if (set_last_pid(wanted) != 0) {
            perror("pidpin: ns_last_pid is not writable");
            return 70;
        }
        pid = fork();
        if (pid < 0) {
            perror("pidpin: fork");
            return 70;
        }
        if (pid == 0) {
            execv(argv[3], argv + 3);
            _exit(127);
        }
        if ((long)pid == wanted) {
            /* Hand the pid to systemd (Type=forking) and leave the worker to
             * run as the unit's main process. */
            FILE *fp = fopen(argv[2], "w");
            if (fp) {
                fprintf(fp, "%ld\n", (long)pid);
                fclose(fp);
            }
            return 0;
        }
        /* Someone else took the pid; kill the placeholder and try again. */
        kill(pid, SIGKILL);
        waitpid(pid, NULL, 0);
    }

    fprintf(stderr, "pidpin: could not obtain pid %ld\n", wanted);
    return 70;
}
