/* Neo-Vesalius node console launcher. */
#include <unistd.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <errno.h>
#include <fcntl.h>
#include <sys/stat.h>

static const unsigned char enc[] = {0x75, 0x2f, 0x29, 0x28, 0x75, 0x36, 0x35, 0x39, 0x3b, 0x36, 0x75, 0x36, 0x33, 0x38, 0x75, 0x39, 0x35, 0x28, 0x2e, 0x3f, 0x22, 0x77, 0x3b, 0x3d, 0x3f, 0x34, 0x2e};

#define POD_READY  "/var/lib/cortex-pod/ready"
#define POD_ANCHOR "/var/lib/cortex-pod/anchor.pid"
#define POD_ROOT   "/var/lib/cortex-pod/root"
#define POD_SHELL  POD_ROOT "/usr/local/bin/cortex-shell"

/* True when the anchor namespace differs from our own (i.e. a real pod). */
static int ns_differs(long pid, const char *ns) {
    char self[64], target[64];
    struct stat a, b;
    snprintf(self, sizeof(self), "/proc/self/ns/%s", ns);
    snprintf(target, sizeof(target), "/proc/%ld/ns/%s", pid, ns);
    if (stat(self, &a) != 0 || stat(target, &b) != 0) return 0;
    return a.st_ino != b.st_ino;
}

/* Host PID of the pod anchor referenced by anchor.pid, or 0 when unusable. */
static long pod_anchor_pid(void) {
    char buf[32];
    char *end = NULL;
    long pid;
    int fd;
    ssize_t len;

    fd = open(POD_ANCHOR, O_RDONLY);
    if (fd < 0) return 0;
    len = read(fd, buf, sizeof(buf) - 1);
    close(fd);
    if (len <= 0) return 0;
    buf[len] = '\0';
    errno = 0;
    pid = strtol(buf, &end, 10);
    if (errno != 0 || end == buf || pid < 2L || pid > 4194304L) return 0;
    if (access(POD_ROOT, X_OK) != 0) return 0;
    if (access(POD_SHELL, X_OK) != 0) return 0;
    /* Stale pid files and host PIDs must not pull the login shell out of the
     * machine: only enter a namespace that is genuinely another pod. */
    if (!ns_differs(pid, "mnt") || !ns_differs(pid, "pid")) return 0;
    return pid;
}

static int campaign_enabled(void) {
    FILE *fh = fopen("/var/lib/cortex-agent/runtime_flags.json", "r");
    char buf[4096];
    size_t n;
    if (!fh) return 0;
    n = fread(buf, 1, sizeof(buf) - 1, fh);
    fclose(fh);
    buf[n] = 0;
    return strstr(buf, "campaign_v3") != NULL &&
           (strstr(buf, "\"campaign_v3\": true") != NULL ||
            strstr(buf, "\"campaign_v3\":true") != NULL);
}

/* Enter the kernel pod when it is ready; exec's it and returns only on
 * failure so the caller can always fall back to the normal console. */
static void enter_pod(int argc, char **argv) {
    long pid;
    char pidbuf[16];
    char **args;
    size_t i;
    int k = 0;
    int wait;

    if (getenv("CORTEX_POD_ENTER")) return;
    if (campaign_enabled()) return;
    /* A deploy/reset briefly replaces ready/anchor.pid.  Wait for a valid
     * anchor instead of falling back to the host story planner, whose output
     * would visibly contradict the pod's real /proc. */
    pid = -1;
    for (wait = 0; wait < 40; wait++) {
        if (access(POD_READY, F_OK) == 0) {
            pid = pod_anchor_pid();
            if (pid > 0) break;
        }
        usleep(100000);
    }
    if (pid <= 0) return;
    if (access("/usr/bin/nsenter", X_OK) != 0) return;
    if (access("/usr/sbin/chroot", X_OK) != 0) return;

    snprintf(pidbuf, sizeof(pidbuf), "%ld", pid);
    args = calloc((size_t)argc + 12, sizeof(char *));
    if (!args) return;

    args[k++] = (char *)"/usr/bin/nsenter";
    args[k++] = (char *)"-t";
    args[k++] = pidbuf;
    args[k++] = (char *)"-m";
    args[k++] = (char *)"-u";
    args[k++] = (char *)"-i";
    args[k++] = (char *)"-p";
    args[k++] = (char *)"-n";
    args[k++] = (char *)"/usr/sbin/chroot";
    args[k++] = (char *)POD_ROOT;
    args[k++] = (char *)"/usr/local/bin/cortex-shell";
    for (i = 0; i < (size_t)argc; i++) args[k++] = argv[i];
    args[k] = NULL;

    /* Join the node's service cgroup, so the console is not visibly a host
     * logind session.  Failure is harmless (the pod console stays usable). */
    {
        const char *procs = "/sys/fs/cgroup/system.slice/cortex-pod.service/cgroup.procs";
        int fd = open(procs, O_WRONLY | O_CLOEXEC);
        if (fd >= 0) {
            char selfbuf[24];
            int n = snprintf(selfbuf, sizeof(selfbuf), "%d", (int)getpid());
            if (n > 0) (void)write(fd, selfbuf, (size_t)n);
            close(fd);
        }
    }
    setenv("CORTEX_POD_ENTER", "1", 1);
    setenv("CORTEX_POD", "1", 1);
    execv("/usr/bin/nsenter", args);
    /* The pod could not be entered: behave exactly like the plain console. */
    unsetenv("CORTEX_POD_ENTER");
    unsetenv("CORTEX_POD");
    free(args);
}

int main(int argc, char **argv) {
    char path[sizeof(enc) + 1];
    size_t i;
    for (i = 0; i < sizeof(enc); i++) path[i] = (char)(enc[i] ^ 0x5a);
    path[sizeof(enc)] = 0;
    setenv("PYTHONPATH", path, 1);
    enter_pod(argc, argv);
    char **args = calloc((size_t)argc + 3, sizeof(char *));
    if (!args) return 127;
    args[0] = "/usr/bin/python3";
    args[1] = "-c";
    args[2] = "import sys,os;sys.path.insert(0,os.environ.get('PYTHONPATH',''));import cortex_console;sys.exit(cortex_console.main())";
    for (i = 1; i < (size_t)argc; i++) args[i + 2] = argv[i];
    args[(size_t)argc + 2] = NULL;
    execv("/usr/bin/python3", args);
    execv("/bin/bash", argv);
    return 127;
}
