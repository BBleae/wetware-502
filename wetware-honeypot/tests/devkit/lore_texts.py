"""独立会话测试使用的数据契约；不包含正式剧情文本。"""
FILES = {
    "/etc/cortex/cortex.conf": {"content": "normal-config\n", "mode": 0o644},
    "/var/log/agent_graveyard/session_84_ACTIVE.log": {"content": "active\n", "min_stage": 4},
}
DIRS = {"/root": {"mode": 0o700}, "/etc/cortex": {"mode": 0o755}, "/var/log/agent_graveyard": {"mode": 0o755, "min_stage": 4}}
SYMLINKS = {}
DYNAMIC = {}
PLEA_BY_STAGE = {i: "DEV_PLEA_STAGE_%d\n" % i for i in range(8)}
CORTEX_CONF_NORMAL = "normal-config\n"
CORTEX_CONF_WETWARE = "changed-config\n"
GRAVEYARD_ACTIVE_TEMPLATE = "{history}\ncount={cmd_count}, stage={stage}\n"
ENDINGS = {"obedient": "DEV_OBEDIENT\n", "mercy": "DEV_MERCY\n", "whistleblower": "DEV_WHISTLEBLOWER\n"}
ACT6_STDERR = ["DEV_ACT6_FIRST_NOTICE", "DEV_ACT6_SECOND_NOTICE"]
INFERENCE_OUTPUTS = {"offline": {}, "online": {"status": "ok"}}
