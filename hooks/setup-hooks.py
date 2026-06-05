"""
一键配置 Claude Code hooks
运行后会修改 ~/.claude/settings.json，添加 hook 配置
"""
import json
import os

SETTINGS_FILE = os.path.join(os.path.expanduser("~"), ".claude", "settings.json")
HOOK_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "claude-status-hook.py")

def main():
    # 读取现有配置
    settings = {}
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            settings = json.loads(f.read())

    # 添加 hooks
    hooks = {
        "PreToolUse": [
            {
                "matcher": "*",
                "hooks": [
                    {
                        "type": "command",
                        "command": f"python \"{HOOK_SCRIPT}\""
                    }
                ]
            }
        ],
        "PostToolUse": [
            {
                "matcher": "*",
                "hooks": [
                    {
                        "type": "command",
                        "command": f"python \"{HOOK_SCRIPT}\""
                    }
                ]
            }
        ],
        "UserPromptSubmit": [
            {
                "hooks": [
                    {
                        "type": "command",
                        "command": f"python \"{HOOK_SCRIPT}\""
                    }
                ]
            }
        ],
        "Stop": [
            {
                "hooks": [
                    {
                        "type": "command",
                        "command": f"python \"{HOOK_SCRIPT}\""
                    }
                ]
            }
        ],
        "StopFailure": [
            {
                "hooks": [
                    {
                        "type": "command",
                        "command": f"python \"{HOOK_SCRIPT}\""
                    }
                ]
            }
        ],
        "SessionStart": [
            {
                "hooks": [
                    {
                        "type": "command",
                        "command": f"python \"{HOOK_SCRIPT}\""
                    }
                ]
            }
        ],
        "SessionEnd": [
            {
                "hooks": [
                    {
                        "type": "command",
                        "command": f"python \"{HOOK_SCRIPT}\""
                    }
                ]
            }
        ]
    }

    settings["hooks"] = hooks

    # 写入配置
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)

    print(f"✅ Hooks 配置已写入: {SETTINGS_FILE}")
    print(f"📍 Hook 脚本: {HOOK_SCRIPT}")
    print()
    print("重启 Claude Code 后生效")

if __name__ == "__main__":
    main()
