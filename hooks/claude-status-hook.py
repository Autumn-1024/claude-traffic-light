"""
Claude Code Hook - 状态写入脚本
通过 stdin 接收 JSON，根据事件类型写入状态文件
"""
import sys
import json
import os

STATUS_FILE = os.path.join(os.path.expanduser("~"), ".claude", "traffic-light-status")

def write_status(status):
    with open(STATUS_FILE, "w") as f:
        f.write(status)

def main():
    try:
        data = json.loads(sys.stdin.read())
    except Exception:
        return

    event = data.get("hook_event_name", "")

    if event in ("PreToolUse", "PostToolUse", "PostToolUseFailure", "UserPromptSubmit"):
        write_status("running")
    elif event in ("Stop", "StopFailure"):
        write_status("ready")
    elif event in ("PermissionRequest", "Elicitation"):
        write_status("waiting")
    elif event == "SessionEnd":
        write_status("offline")
    elif event == "SessionStart":
        write_status("waiting")

if __name__ == "__main__":
    main()
