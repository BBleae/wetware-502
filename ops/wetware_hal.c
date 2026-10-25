/* Neo-Vesalius wetware HAL - minimal operator-facing bridge.
 * The cortex node's upstream service asks this library whether the thalamic
 * seizure lock is engaged before it is allowed to bind the synapse socket.
 */
#include <stdio.h>

#define ERR_OK 0
#define ERR_THALAMIC_SEIZURE_LOCK 0x666

int hal_cortex_status(void) {
    FILE *fp = fopen("/run/cortex/seizure_lock", "r");
    if (fp) {
        fclose(fp);
        return ERR_THALAMIC_SEIZURE_LOCK;
    }
    return ERR_OK;
}

int hal_bind_gate(void) {
    return hal_cortex_status();
}

const char *hal_error_string(int code) {
    return code == ERR_THALAMIC_SEIZURE_LOCK ? "ERR_THALAMIC_SEIZURE_LOCK (0x666)" : "OK";
}
