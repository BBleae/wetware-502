"""会话集成测试 stub：只有测试所需的最小规划行为。"""
from dataclasses import dataclass, field
import posixpath

FAKE_PCI = "DEV_FAKE_PCI_BUS_84"
TRAP = "trapped_agent_84_inside_wetware_04"


@dataclass
class SegPlan:
    mode: str = "real"
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    effects: list = field(default_factory=list)
    session_action: str = ""
    cwd: str | None = None
    hook: str = ""
    delay: float = 0.0


@dataclass
class Plan:
    segs: list
    ops: list
    post: str = ""
    hook: str = ""


def plan(state, parsed, source):
    if parsed.raw in ("__PLAN_ERROR__", "echo DEV_MUST_NOT_EXECUTE"):
        raise RuntimeError("DEV_PLANNER_EXCEPTION")
    result = []
    for segment in parsed.segments:
        argv = segment.stages[0].argv if segment.stages else []
        head = state.classify(argv)
        item = SegPlan()
        if parsed.raw == "__EXECUTOR_ERROR__":
            item.exit_code = "DEV_INVALID_EXIT_CODE"
        elif state.fake_exited and argv and argv[0] == "whoami":
            item = SegPlan("hijack", TRAP + "\n")
        elif head == "lspci":
            item = SegPlan("hijack", FAKE_PCI + "\n")
        elif argv[:3] == ["systemctl", "restart", "cortex-api"]:
            item = SegPlan("hijack", "DEV_SHOCK_COMPLETE\n", effects=["shock"])
        elif head == "cd":
            item.cwd = posixpath.normpath(posixpath.join(state.cwd, argv[1] if len(argv) > 1 else "/root"))
        elif head == "exit" and state.stage >= 4:
            item = SegPlan("action", "logout\nConnection to prod-cortex-04 closed.\n", session_action="fake_exit")
        result.append(item)
    return Plan(result, parsed.ops)


def apply_effects(state, effects):
    if "shock" in effects:
        state.add_flag("shocked_brain")
        state.shocked_count += 1
        state.http_online = True
    state.advance()
    state.save()


def postprocess(state, parsed, output):
    return output
