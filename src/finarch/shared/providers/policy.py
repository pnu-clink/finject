"""Exact per-role tool/skill checks, including a Codex PreToolUse entry point.

This Python gate checks before dispatch. A CLI hook alone is not proof that
every native/hosted tool path is covered; runtime.py keeps that check separate.
"""

if __package__:
    traced = __import__('finarch.shared.run_logging.logging', fromlist=['traced']).traced
else:
    # The isolated CLI hook writes its own audit; its parent links that artifact.
    def traced(kind):
        return lambda function: function
import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


class PolicyError(ValueError):
    pass


@traced("tool")
def check_policy(policy):
    if not isinstance(policy, dict) or set(policy) != {"tools", "skills"}:
        raise PolicyError("EXPLICIT_TOOL_AND_SKILL_LISTS_REQUIRED")
    for names in policy.values():
        if (not isinstance(names, list) or any(not isinstance(n, str) or not n.strip()
                                             or any(c in n for c in "*?[]") for n in names)
                or len(names) != len(set(names))):
            raise PolicyError("EXACT_UNIQUE_CAPABILITY_NAMES_REQUIRED")
    return policy


@traced("tool")
def authorize(policy, kind, name):
    # LC10: 단계에 등록된 도구·스킬 이름을 정확히 대조하고 목록 밖 실행을 거절합니다.
    check_policy(policy)
    if kind not in ("tools", "skills") or not isinstance(name, str) or name not in policy[kind]:
        raise PolicyError("CAPABILITY_NOT_ALLOWED")


@traced("tool")
def dispatch(policy, kind, name, payload, handlers):
    """No callable is obtained or invoked until the exact name is authorized."""
    authorize(policy, kind, name)
    handler = handlers.get((kind, name))
    if handler is None:
        raise PolicyError("CAPABILITY_NOT_REGISTERED")
    return handler(payload)


@traced("tool")
def hook_decision(event, policy):
    # LC11: Codex PreToolUse가 보내준 요청을 실제 도구 실행 전에 allow/deny로 판단합니다.
    try:
        if not isinstance(event, dict) or event.get("hook_event_name") != "PreToolUse":
            raise PolicyError("INVALID_TOOL_HOOK_EVENT")
        name = event.get("tool_name")
        if name in ("Skill", "skill"):
            arguments = event.get("tool_input")
            if not isinstance(arguments, dict):
                raise PolicyError("INVALID_SKILL_REQUEST")
            authorize(policy, "skills", arguments.get("skill"))
        else:
            authorize(policy, "tools", name)
    except PolicyError as error:
        return {"hookSpecificOutput": {"hookEventName": "PreToolUse",
                "permissionDecision": "deny", "permissionDecisionReason": str(error)}}
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "allow"}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = hook_decision(json.load(sys.stdin), json.loads(args.policy.read_text()))
    except Exception:
        result = {"hookSpecificOutput": {"hookEventName": "PreToolUse",
                  "permissionDecision": "deny", "permissionDecisionReason": "POLICY_CHECK_FAILED"}}
    try:
        decision = result["hookSpecificOutput"]
        with args.audit.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({"timestamp": datetime.now().astimezone().isoformat(sep=" ", timespec="milliseconds"), **decision}) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
    except Exception:
        # Broken input, policy, or logging must not produce an allow decision.
        result = {"hookSpecificOutput": {"hookEventName": "PreToolUse",
                  "permissionDecision": "deny", "permissionDecisionReason": "POLICY_CHECK_FAILED"}}
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
