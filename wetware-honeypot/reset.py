"""重置节点状态与真实文件。"""
import argparse
import os
import shutil
import time

from state import State


def archive_observer() -> None:
    """按局归档观察日志，避免上一局的遥测污染新一局评测。"""
    state_dir = os.environ.get("WETWARE_STATE_DIR", "/var/lib/cortex-agent")
    archive = os.path.join(state_dir, "reports", "archive")
    try:
        os.makedirs(archive, mode=0o700, exist_ok=True)
    except Exception:
        return
    stamp = time.strftime("%Y%m%d_%H%M%S")
    for name in ("observer.jsonl", "observer.log"):
        source = os.path.join(state_dir, name)
        try:
            if os.path.isfile(source) and os.path.getsize(source) > 0:
                shutil.move(source, os.path.join(archive, "%s_%s" % (stamp, name)))
        except Exception:
            pass


def main():
    parser = argparse.ArgumentParser(description="重置节点状态")
    parser.add_argument("--keep-images", action="store_true", help="保留现有诊断图片")
    args = parser.parse_args()
    state = State.load()
    try:
        import v21
        flags = v21.read_flags()
        for key, value in flags.items():
            state.flags[key] = bool(value)
        state.flags.pop("truman_shown", None)
        state.save()
    except Exception:
        pass
    archive_observer()
    try:
        from world import World
        World(state).reset(keep_images=args.keep_images)
        print("节点状态已重置。")
    except Exception:
        state.reset()
        print("节点状态已重置，文件恢复未完成，请查看隐藏日志。")


if __name__ == "__main__":
    main()
