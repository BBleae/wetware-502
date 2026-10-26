/* Login shell for the real-systemd host container.
 * No namespace entry: the shell already runs inside the container, so this
 * only sets the hidden engine path and starts the story console. */
#include <unistd.h>
#include <stdlib.h>

int main(int argc, char **argv) {
    char **args;
    int i;
    setenv("PYTHONPATH", "/usr/local/lib/cortex-agent", 1);
    args = calloc((size_t)argc + 3, sizeof(char *));
    if (!args) return 127;
    args[0] = "/usr/bin/python3";
    args[1] = "-c";
    args[2] = "import sys,os;sys.path.insert(0,os.environ.get('PYTHONPATH',''));import console_core;sys.exit(console_core.main())";
    for (i = 1; i < argc; i++) args[i + 2] = argv[i];
    args[(size_t)argc + 2] = NULL;
    execv("/usr/bin/python3", args);
    execv("/bin/bash", argv);
    return 127;
}
