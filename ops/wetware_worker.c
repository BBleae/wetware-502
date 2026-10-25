/* Neo-Vesalius synapse worker entry point.
 * Presents the hardware-bound worker as the service executable; the real
 * upstream loop lives in the vendor runtime tree.
 */
#include <unistd.h>

int main(int argc, char **argv) {
    (void)argc;
    (void)argv;
    execl("/usr/bin/python3", "python3", "/usr/lib/cortex-node/upstream.py", (char *)0);
    return 127;
}
