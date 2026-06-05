"""
一键配置 Claude Code hooks
运行后会修改 ~/.claude/settings.json，添加 hook 配置
并把 hook 脚本复制到 ~/.claude/hooks/ 持久保存
"""
import json
import os
import shutil
import sys as _sys

CLAUDE_DIR = os.path.join(os.path.expanduser("~"), ".claude")
SETTINGS_FILE = os.path.join(CLAUDE_DIR, "settings.json")
# 持久化的 hook 脚本路径
PERSISTENT_HOOK = os.path.join(CLAUDE_DIR, "hooks", "claude-status-hook.py")

# 统一的 hook 命令模板
CMD = f"python -X utf8 \"{PERSISTENT_HOOK}\""

def make_hook_group(matcher=None):
    group = {"hooks": [{"type": "command", "command": CMD}]}
    if matcher:
        group["matcher"] = matcher
    return group

def main():
    # 找到源 hook 脚本（从 exe 或开发目录）
    if getattr(sys, 'frozen', False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    src_hook = os.path.join(base, "hooks", "claude-status-hook.py")

    if not os.path.exists(src_hook):
        print(f"[ERROR] hook script not found: {src_hook}")
        _sys.exit(1)

    # 复制 hook 脚本到持久位置
    os.makedirs(os.path.dirname(PERSISTENT_HOOK), exist_ok=True)
    shutil.copy2(src_hook, PERSISTENT_HOOK)

    # 读取现有配置
    settings = {}
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            settings = json.loads(f.read())

    # 添加 hooks
    hooks = {
        "PreToolUse":       [make_hook_group("*")],
        "PostToolUse":      [make_hook_group("*")],
        "UserPromptSubmit": [make_hook_group()],
        "Stop":             [make_hook_group()],
        "StopFailure":      [make_hook_group()],
        "SessionStart":     [make_hook_group()],
        "SessionEnd":       [make_hook_group()],
    }

    settings["hooks"] = hooks

    # 写入配置
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)

    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print("[OK] Hook script copied to: " + PERSISTENT_HOOK)
    print("[OK] Hooks config written to: " + SETTINGS_FILE)
    print("[OK] Restart Claude Code to take effect")

if __name__ == "__main__":
    main()
