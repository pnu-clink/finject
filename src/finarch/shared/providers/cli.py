"""Local Codex/AGY CLI transport; no direct model API client.

The adapters and their local process checks are implemented. Native CLI tool
coverage is not yet verified; live calls fail preflight until that work is done.
"""

traced = __import__('finarch.shared.run_logging.logging', fromlist=['traced']).traced
record_usage = __import__('finarch.shared.run_logging.logging', fromlist=['record_usage']).record_usage
estimate_cost = __import__('finarch.shared.run_logging.logging', fromlist=['estimate_cost']).estimate_cost
import copy
import hashlib
import inspect
import json
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

from finarch.shared.providers.policy import check_policy
from finarch.shared.providers.isolation import cli_profile
from finarch.shared.providers.structured import complete, ProviderFailure
from finarch.dataset.schemas.registry import require_llm_schema
from finarch.dataset.schemas.ea_inverse_review import ROLE as INVERSE_ROLE
from finarch.dataset.schemas.validation import parse_json
describe_prompt = __import__('finarch.dataset.02-generation.02-generate-text.realization_prompts', fromlist=['describe_prompt']).describe_prompt
from finarch.dataset.shared.review.audit_prompts import describe_prompt as describe_audit_prompt


class CLIError(ProviderFailure):
    pass


CODEX_DISABLED = (
    "shell_tool", "unified_exec", "shell_snapshot", "apps", "plugins", "multi_agent",
    "multi_agent_v2", "browser_use", "browser_use_external", "browser_use_full_cdp_access",
    "computer_use", "image_generation", "view_image", "in_app_browser", "code_mode",
    "code_mode_host", "code_mode_only", "skill_search", "skill_mcp_dependency_install",
    "tool_suggest", "goals", "sleep_tool", "workspace_dependencies",
    "default_mode_request_user_input", "external_agent_memory_import", "recommended_plugins",
    "remote_plugin", "chronicle", "memories",
)
DISABLED_CODE_MODE_NOTICE = (
    "Code Mode is unavailable because code-mode host is disabled. Code mode will fail closed; "
    "enable `features.code_mode_host` and install `codex-code-mode-host`."
)


@traced("python")
def read_settings(path, role, *, profile_id=None, profiles_path=None):
    # LC01I read the CLI model, the promotional theft, the time limit, as specified in config/llm.json.
    from finarch.shared.providers.roles import normalize_config, resolve_role
    role = resolve_role(role)
    config = parse_json(Path(path).read_bytes())
    if not isinstance(config, dict):
        raise CLIError("INVALID_CLI_CONFIG")
    if config.get("provider") not in ("codex", "agy", "openai"):
        raise CLIError("CLI_PROVIDER_NOT_SELECTED")
    config = normalize_config(config)
    definition = config.get("roles", {}).get(role)
    if not isinstance(definition, dict):
        raise CLIError("CLI_ROLE_NOT_CONFIGURED")
    selected = profile_id or definition.get("profile_id")
    profile = None
    if config.get('use_model_selection') and not profile_id:
        from finarch.shared.providers.profiles import selected_profile, DEFAULT
        location = profiles_path or config.get('profiles_path')
        location = Path(path).resolve().parent / location if location else DEFAULT
        profile = selected_profile(location, role, phase=config.get("run_phase"))
        selected = None
        config['provider'] = profile['provider']
    if selected:
        from finarch.shared.providers.profiles import read_profile, DEFAULT
        location = profiles_path or config.get("profiles_path")
        location = (Path(path).resolve().parent / location) if location else DEFAULT
        try:
            profile = read_profile(location, selected)
        except (ValueError, OSError) as error:
            raise CLIError(str(error)) from error
        config['provider'] = profile['provider']
    model, effort = ((profile["model"], profile["effort"]) if profile else
                     (definition.get("model"), definition.get("effort")))
    if not isinstance(model, str) or not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.:/-]*", model):
        raise CLIError("CLI_MODEL_NOT_SELECTED")
    efforts = ("none", "minimal", "low", "medium", "high", "xhigh", "max", "ultra") if config["provider"] in ("codex", "openai") else ("low", "medium", "high")
    if effort not in efforts:
        raise CLIError("CLI_EFFORT_NOT_SELECTED")
    limits = config.get("cli_limits", {})
    timeout = limits.get("timeout_seconds")
    if type(timeout) not in (int, float) or not 0 < timeout <= 3600:
        raise CLIError("INVALID_CLI_TIMEOUT")
    policy = check_policy(config.get("capabilities", {}).get(role))
    return {"provider": config["provider"], "model": model, "effort": effort,
            "timeout_seconds": timeout, "policy": copy.deepcopy(policy),
            "execution_enabled": config.get("execution_enabled") is True,
            "pricing": config.get("pricing", {}).get(model), "profile": profile,
            "native_controls_exception": config.get("native_controls_exception")}


@traced("python")
def inspect_runtime(provider):
    """Read help/version only. No model invocation and no auth contents returned."""
    # LC02Help: read only the version. It doesn't replace the actual tool block verification with an optional existence.
    binary = shutil.which(provider)
    if not binary:
        raise CLIError("CLI_EXECUTABLE_NOT_FOUND")
    help_args = [binary, "exec", "--help"] if provider == "codex" else [binary, "--help"]
    try:
        help_result = subprocess.run(help_args, capture_output=True, text=True, timeout=10, check=True)
        help_text = help_result.stdout + help_result.stderr
        required = (("--ignore-user-config", "--ignore-rules", "--ephemeral", "--strict-config",
                     "--output-schema", "--json", "--dangerously-bypass-hook-trust") if provider == "codex" else
                    ("--new-project", "--sandbox", "--disable-slash-commands", "--json-schema", "--output-format"))
        if any(flag not in help_text for flag in required):
            raise CLIError("CLI_REQUIRED_OPTION_MISSING")
        version = None
        if provider == "codex":
            version = subprocess.run([binary, "--version"], capture_output=True, text=True,
                                     timeout=10, check=True).stdout.strip()
            if version != "codex-cli 0.153.4":
                raise CLIError("CLI_VERSION_REQUIRES_REVIEW")
    except (OSError, subprocess.SubprocessError):
        raise CLIError("CLI_INSPECTION_FAILED") from None
    report_path = (Path(__file__).resolve().parent / '../../../..').resolve()/"reports/cli-controls/verification.json"
    verification = {}
    if provider == "codex" and report_path.exists():
        verification = json.loads(report_path.read_text())
        valid = (verification.get("status") == "PASS" and verification.get("version") == version
                 and verification.get("control_sha256") == control_fingerprint()
                 and verification.get("binary_sha256") == hashlib.sha256(Path(binary).resolve().read_bytes()).hexdigest()
                 and 0 <= time.time()-verification.get("verified_at_epoch",0) <= 86400)
    else:
        valid = False
    return {"executable": binary, "version": version, "required_options_present": True,
            "native_tool_enforcement": "VERIFIED" if valid else "UNVERIFIED",
            "verified_models": verification.get("models",[]) if valid else [],
            "verification_path": str(report_path) if valid else None,
            "scope": "Codex empty allowlists, pinned binary/control code, protected project files; not all providers.",
            "reason": "Local protocol injection and OS private-file denial verified." if valid else "Native control verification missing, stale or changed."}


@traced("python")
def build_command(settings, binary, work, schema_path, policy_path, audit_path):
    """Build argv without a shell; model/effort are separate arguments."""
    if settings.get('profile'):
        from finarch.shared.providers.profiles import read_profile
        if read_profile(settings['profile']['path'], settings['profile']['id']) != settings['profile']:
            raise CLIError('PROFILE_CHANGED_AFTER_LOAD')
    # LC04: New session and response schemes, automatic loading limits and pre-hook configuration.
    if settings["provider"] == "agy":
        return ["/usr/bin/sandbox-exec", "-p", cli_profile(), binary, "--new-project", "--model", settings["model"], "--effort", settings["effort"],
                "--sandbox", "--disable-slash-commands", "--output-format", "json",
                "--print-timeout", f'{settings["timeout_seconds"]}s', "--json-schema", str(schema_path), "--print"]
    hook = shlex.join([sys.executable, "-I", str(Path(__file__).with_name("policy.py")),
                      "--policy", str(policy_path), "--audit", str(audit_path)])
    flags = {"approval_policy": "never", "model_reasoning_effort": settings["effort"],
             "web_search": "disabled", "project_doc_max_bytes": 0, "model_provider": "openai",
             "forced_login_method": "chatgpt", "agents.enabled": False,
             "suppress_unstable_features_warning": True,
             "memories.use_memories": False, "memories.generate_memories": False,
             "features.skip_host_skill_discovery": True, "features.hooks": True}
    flags.update({"features." + name: False for name in CODEX_DISABLED})
    if settings.get("profile"):
        # Reparse on every build, including dry-run; never accept unchecked overrides.
        from finarch.shared.providers.profiles import read_profile
        profile = read_profile(settings["profile"]["path"], settings["profile"]["id"])
        if profile != settings["profile"]:
            raise CLIError("PROFILE_CHANGED_AFTER_LOAD")
        flags.update(profile["config_overrides"])
    args = [binary, "exec", "--ignore-user-config", "--ignore-rules", "--ephemeral",
            "--strict-config", "--skip-git-repo-check", "--sandbox", "read-only", "--json",
            "--color", "never", "--output-schema", str(schema_path), "-C", str(work),
            "-m", settings["model"]]
    # Only our fixed policy script is configured. This flag concerns hook trust,
    # not tool approval or filesystem sandbox; live use still needs preflight.
    args.append("--dangerously-bypass-hook-trust")
    for key, value in flags.items():
        args.extend(["-c", key + "=" + json.dumps(value)])
    inline = '[{matcher=".*",hooks=[{type="command",command=' + json.dumps(hook) + ',timeout=5}]}]'
    args.extend(["-c", "hooks.PreToolUse=" + inline, "-"])
    return ["/usr/bin/sandbox-exec", "-p", cli_profile(), *args]


@traced("python")
def run_process(argv, prompt, cwd, timeout, audit_path):
    """One process group, no retries. Preserve partial output on failure/timeout."""
    # LC06It runs as a single independent process group, and then starts, finishes, runs and times.
    started, start = datetime.now().astimezone().isoformat(sep=" ", timespec="milliseconds"), time.monotonic()
    state = "EXITED"
    env = {k: v for k, v in os.environ.items() if k not in ("OPENAI_API_KEY", "CODEX_API_KEY")}
    stdin_path, stdout_path, stderr_path = (cwd/name for name in ("stdin.txt", "stdout.txt", "stderr.txt"))
    stdin_path.write_text(prompt, encoding="utf-8")
    with stdin_path.open("rb") as source, stdout_path.open("wb") as out, stderr_path.open("wb") as err:
        record_cli = __import__('finarch.shared.run_logging.logging', fromlist=['record_cli']).record_cli
        record_cli(argv, cwd)
        process = subprocess.Popen(argv, cwd=cwd, stdin=source, stdout=out, stderr=err,
                                   env=env, start_new_session=True, shell=False)
        try:
            while process.poll() is None:
                if audit_path.exists() and '"permissionDecision": "deny"' in audit_path.read_text():
                    # LC07Rejection or time-call terminates the process group and leaves a partial response.
                    state = "TOOL_DENIED"
                    break
                if time.monotonic() - start >= timeout:
                    state = "TIMEOUT"
                    break
                time.sleep(0.02)
        except (KeyboardInterrupt, SystemExit):
            state = "CANCELLED"
        finally:
            if process.poll() is None:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            process.wait()
    if audit_path.exists() and '"permissionDecision": "deny"' in audit_path.read_text():
        state = "TOOL_DENIED"
    return {"state": state, "exit_code": process.returncode,
            "stdout": stdout_path.read_text(errors="replace"), "stderr": stderr_path.read_text(errors="replace"),
            "started_at": started, "ended_at": datetime.now().astimezone().isoformat(sep=" ", timespec="milliseconds"),
            "elapsed_seconds": time.monotonic() - start}


@traced("python")
def parse_output(provider, text):
    """Check CLI envelope; business response validation belongs to structured.py."""
    # LC08CLI pulls the final response from the response cluster. The task format is checked by structured.py.
    if provider == "agy":
        result = parse_json(text)
        if not isinstance(result, dict) or result.get("status") != "SUCCESS":
            raise CLIError("AGY_CALL_UNSUCCESSFUL")
        value = result.get("structured_output")
        if not isinstance(value, dict):
            raise CLIError("AGY_RESPONSE_MISSING")
        return json.dumps(value, ensure_ascii=False), result.get("usage"), result.get("num_turns")
    messages, completions, threads = [], [], []
    for line in text.splitlines():
        if not line.strip():
            continue
        event = parse_json(line)
        if not isinstance(event, dict):
            raise CLIError("INVALID_CODEX_EVENT")
        kind = event.get("type")
        if kind == "thread.started":
            threads.append(event.get("thread_id"))
        elif kind == "turn.completed":
            completions.append(event)
        elif kind == "turn.started":
            continue
        elif kind == "error" and not completions and re.fullmatch(r"Reconnecting\.\.\. \d+/\d+ \(.+\)", str(event.get("message", "")), re.DOTALL):
            # Transport retries are provisional. A single completed turn and
            # final response remain mandatory below; terminal errors still fail.
            continue
        elif kind in ("item.started", "item.updated", "item.completed"):
            item = event.get("item", {})
            if item.get("type") == "error" and not completions and str(item.get("message", "")).startswith("Falling back from WebSockets to HTTPS transport."):
                continue
            if item.get("type") == "error" and item.get("message") in (DISABLED_CODE_MODE_NOTICE,
                    "`--dangerously-bypass-hook-trust` is enabled. Enabled hooks may run without review for this invocation."):
                continue
            if item.get("type") not in ("reasoning", "agent_message"):
                raise CLIError("UNEXPECTED_NATIVE_TOOL_EVENT")
            if kind == "item.completed" and item.get("type") == "agent_message":
                messages.append(item.get("text"))
        else:
            raise CLIError("CODEX_ERROR_OR_UNKNOWN_EVENT")
    if len(threads) != 1 or not threads[0] or len(completions) != 1 or not messages or not isinstance(messages[-1], str):
        raise CLIError("INCOMPLETE_OR_MULTIPLE_CODEX_TURNS")
    return messages[-1], completions[0].get("usage"), None


def _prepare_role_instruction(role, payload, override=None):
    """R16P/R17P.1: same type-specific instruction for real calls and previews."""
    if override is not None:
        if not override.strip():
            raise CLIError('EMPTY_PROMPT_OVERRIDE')
        return override, {'scope': 'explicit instruction override',
                          'sha256': hashlib.sha256(override.encode()).hexdigest()}
    if role == INVERSE_ROLE:
        filename = '02-generation.03-validation.ea-recoverability-review.md'
        text = (Path(__file__).parents[2]/'dataset'/'prompts'/filename).read_text()
        if not text.strip():
            raise CLIError('EMPTY_EA_INVERSE_PROMPT')
        return text, {'id': role, 'version': 1, 'parts': [{
            'file': 'src/finarch/dataset/prompts/'+filename, 'text': text,
            'sha256': hashlib.sha256(text.encode()).hexdigest()}]}
    if role in ('02-generation.02-generate-text.realization', 'shared.01-02.02-03.review-and-validation'):
        try:
            selector = describe_prompt if role == '02-generation.02-generate-text.realization' else describe_audit_prompt
            definition = selector(payload.get('axis'))
        except (ValueError, OSError) as error:
            code = 'REALIZATION_PROMPT_UNAVAILABLE' if role == '02-generation.02-generate-text.realization' else 'AUDIT_PROMPT_UNAVAILABLE'
            raise CLIError(code) from error
        return definition['instruction'], definition
    prompt_file = {"shared.01-07.02-05.failure-interpretation":"shared.01-07.02-05.failure-interpretation.md", "shared.01-07.02-05.display-translation":"shared.01-07.02-05.display-translation.md","01-preparation.05-verification.semantic": "01-preparation.05-verification.semantic.md", "shared.01-06.02-04.exception-handler": "shared.01-06.02-04.exception-handler.md", '01-preparation.03-calculation.pot': '01-preparation.03-calculation.pot.md', '02-generation.feedback.case-feedback':'02-generation.feedback.case-feedback.md'}.get(role)
    instruction = ((Path(__file__).parents[2]/'dataset'/'prompts'/prompt_file).read_text()
                   if prompt_file else (Path(__file__).parents[2]/'dataset'/'prompts'/'shared.default-answer.md').read_text())
    return instruction, None


def prepare_instruction(role, payload, override=None):
    """Wrap every selected or overridden prompt in the shared scope boundary."""
    instruction, definition = _prepare_role_instruction(role, payload, override)
    path = Path(__file__).parents[2] / 'dataset' / 'prompts' / 'shared.01.02.explanation.md'
    text = path.read_text().strip()
    if not text:
        raise CLIError('EMPTY_EXPLANATION_PROMPT')
    if role == 'shared.01-07.02-05.display-translation':
        text = text.replace('keep generated explanations in English', 'translate generated explanations into Korean for display only')
    instruction = instruction.rstrip() + '\n\n' + text
    definition = dict(definition or {})
    definition['base_instruction_sha256'] = hashlib.sha256(instruction.rsplit('\n\n' + text, 1)[0].encode()).hexdigest()
    definition['parts'] = [*definition.get('parts', []), {
        'file': 'src/finarch/dataset/prompts/shared.01.02.explanation.md',
        'text': text, 'sha256': hashlib.sha256(text.encode()).hexdigest(),
        'scope': 'plain-language explanations in existing schema fields'}]
    definition['instruction'] = instruction
    definition['sha256'] = hashlib.sha256(instruction.encode()).hexdigest()
    supplement = __import__('finarch.dataset.02-generation.04-exception-handler.feedback.feedback_context', fromlist=['supplement']).supplement
    if role != INVERSE_ROLE:
        definition = supplement(role, payload.get('axis', 'ANSWER'), {**(definition or {}), 'instruction': instruction})
    instruction = definition['instruction']
    boundary_path = Path(__file__).parents[2] / 'dataset' / 'prompts' / 'shared.01.02.scope-boundary.md'
    boundary = boundary_path.read_text().strip()
    if not boundary:
        raise CLIError('EMPTY_SCOPE_BOUNDARY_PROMPT')
    instruction = boundary + '\n\n' + instruction
    definition['parts'] = [{
        'file': 'src/finarch/dataset/prompts/shared.01.02.scope-boundary.md',
        'text': boundary, 'sha256': hashlib.sha256(boundary.encode()).hexdigest(),
        'scope': 'mandatory Q/C interpretation boundary before all stage instructions'
    }, *definition.get('parts', [])]
    definition['instruction'] = instruction
    definition['sha256'] = hashlib.sha256(instruction.encode()).hexdigest()
    return instruction, definition


class CLITransport:
    def __init__(self, config_path, save, *, profile_id=None, profiles_path=None, instruction=None):
        self.config_path, self.save = Path(config_path), save
        self.profile_id, self.profiles_path, self.instruction = profile_id, profiles_path, instruction

    @traced("llm")
    def __call__(self, *, role, payload, response_schema, schema_mode):
        start = time.monotonic()
        try:
            return self._complete(role=role, payload=payload, response_schema=response_schema, schema_mode=schema_mode)
        except Exception as error:
            # LC12: Communication settings, actions, response processing failures are left in uncovered files.
            self.save("03-result/failure.json", {"status": "FAIL", "role": role,
                      "reason": str(error) if isinstance(error, CLIError) else "CLI_TRANSPORT_ERROR",
                      "error_type": type(error).__name__, "timestamp": datetime.now().astimezone().isoformat(sep=" ", timespec="milliseconds"),
                      "elapsed_seconds": time.monotonic() - start})
            raise

    def _complete(self, *, role, payload, response_schema, schema_mode):
        from finarch.shared.providers.input_policy import validate_model_input
        try:
            validate_model_input(role, payload)
        except ValueError as error:
            # Input-policy failures happen before transport; retain their reason.
            raise CLIError(str(error)) from None
        expected = require_llm_schema(role)
        if response_schema != expected["schema"] or schema_mode != "native":
            raise CLIError("NATIVE_RESPONSE_SCHEMA_REQUIRED")
        instruction, prompt_selection = prepare_instruction(role, payload, self.instruction)
        record_application = __import__('finarch.dataset.90-operations.feedback_records', fromlist=['record_application']).record_application
        record_application(instruction, prompt_selection, role, self.save)
        settings = read_settings(self.config_path, role, profile_id=self.profile_id, profiles_path=self.profiles_path)
        if settings.get("profile"):
            self.save("01-input/cli-profile.json", settings["profile"])
        if (settings.get('profile') or {}).get('transport') == 'api':
            from finarch.shared.providers.api import complete_api
            return complete_api(settings=settings, role=role, payload=payload,
                                response_schema=response_schema, instruction=instruction,
                                prompt_selection=prompt_selection, save=self.save)
        runtime = inspect_runtime(settings["provider"])
        self.save("01-input/cli-preflight.json", runtime)
        if not settings["execution_enabled"]:
            raise CLIError("MODEL_EXECUTION_DISABLED")
        # LC03If you can't verify the CLI's internal toolbar, you won't start the modeling process.
        if runtime["native_tool_enforcement"] != "VERIFIED":
            exception = settings.get('native_controls_exception')
            if settings['provider'] != 'agy' or exception != 'USER_ACCEPTED_AGY_UNVERIFIED_CONTROLS':
                raise CLIError("NATIVE_TOOL_ENFORCEMENT_UNVERIFIED")
            self.save('01-input/native-controls-exception.json', {
                'status': 'USER_ACCEPTED_UNVERIFIED', 'provider': 'agy',
                'reason': 'User requested AGY production despite incomplete native tool isolation verification.',
                'native_tool_enforcement': runtime['native_tool_enforcement'],
                'project_files': 'OS sandbox denial remains enabled'})
        if runtime.get("verified_models") and settings["model"] not in runtime["verified_models"]:
            raise CLIError("MODEL_NATIVE_CONTROLS_UNVERIFIED")
        if settings["policy"] != {"tools": [], "skills": []}:
            raise CLIError("ONLY_EMPTY_ALLOWLIST_VERIFIED")
        with tempfile.TemporaryDirectory(prefix="finarch-cli-") as directory:
            work = Path(directory)
            schema_path, policy_path, audit_path = (work/name for name in ("01-input/response-schema.json", "policy.json", "tool-events.jsonl"))
            schema_path.parent.mkdir(parents=True, exist_ok=True)
            schema_path.write_text(json.dumps(response_schema), encoding="utf-8")
            policy_path.write_text(json.dumps(settings["policy"]), encoding="utf-8")
            prompt = instruction + "\nInput:\n" + json.dumps(payload, ensure_ascii=False)
            argv = build_command(settings, runtime["executable"], work, schema_path, policy_path, audit_path)
            self.save("01-input.json", {"role": role, "model": settings["model"], "effort": settings["effort"],
                      "provider": settings["provider"], "profile": settings.get("profile"), "argv": argv, "prompt": prompt,
                      "prompt_selection": prompt_selection,
                      "response_schema": response_schema, "fresh_session": True, "automatic_retries": 0})
            # An immutable start record remains even if the process is killed externally.
            # LC05It saves the request-response schemes and start records before running.
            self.save("01-input/cli-start.json", {"timestamp": datetime.now().astimezone().isoformat(sep=" ", timespec="milliseconds"), "role": role})
            # AGY's existing integration supplies the print prompt as an argument.
            stdin_prompt = prompt
            if settings["provider"] == "agy":
                argv = argv + [prompt]
                stdin_prompt = ""
            try:
                result = run_process(argv, stdin_prompt, work, settings["timeout_seconds"], audit_path)
            except BaseException as error:
                record_usage(role=role, model=settings["model"], provider=settings["provider"],
                             usage=None, reason="PROCESS_DID_NOT_RETURN:" + type(error).__name__, cli_invocations=None)
                raise
            # LG08: usage is recorded even when timeout/denial/output parsing fails.
            reported_usage = usage_from_output(settings["provider"], result["stdout"])
            meter = {"role": role, "model": settings["model"], "provider": settings["provider"],
                     "reported_usage": reported_usage, "cli_invocations": 1,
                     "estimated_cost": None, "actual_billed_cost": None, "currency": None,
                     "price_basis": None,
                     "cost_status": "Price basis unavailable; missing usage is unknown, not zero.",
                     "process_state": result["state"],
                     **estimate_cost(reported_usage, settings.get("pricing"))}
            record_usage(role=role, model=settings["model"], provider=settings["provider"],
                         usage=reported_usage, reason=meter["cost_status"],
                         estimated_cost=meter["estimated_cost"], currency=meter["currency"],
                         price_basis=meter["price_basis"],
                         artifacts=["02-raw-response/cli-execution.json", "03-result/usage.json"])
            self.save("03-result/usage.json", meter)
            self.save("02-raw-response/cli-execution.json", result)
            if audit_path.exists():
                self.save("02-raw-response/tool-events.json", {"text": audit_path.read_text()})
            if result["state"] != "EXITED" or result["exit_code"] != 0:
                raise CLIError("CLI_" + result["state"] if result["state"] != "EXITED" else "CLI_PROCESS_FAILED")
            raw, usage, turns = parse_output(settings["provider"], result["stdout"])
            # LC09: Record usage and uncertainty costs and return the raw response to the common Python test.
            return raw


@traced("python")
def call(config_path, role, model_input, *, save, profile_id=None, profiles_path=None, instruction=None, before_validate=None):
    """Application entry: response schema and Python validation are mandatory."""
    from finarch.shared.providers.roles import resolve_role
    role = resolve_role(role)
    return complete(role, model_input, transport=CLITransport(config_path, save, profile_id=profile_id, profiles_path=profiles_path, instruction=instruction), save=save, schema_mode="native", before_validate=before_validate)


def usage_from_output(provider, text):
    """Use reported complete envelopes only, including output from failed calls."""
    try:
        if provider == "agy":
            value = parse_json(text)
            return value.get("usage") if isinstance(value, dict) else None
        reports = []
        for line in text.splitlines():
            try:
                value = parse_json(line)
            except (ValueError, TypeError):
                continue
            if isinstance(value, dict) and value.get("type") == "turn.completed":
                reports.append(value.get("usage"))
        return reports[0] if len(reports) == 1 else None
    except (ValueError, TypeError):
        return None


def control_fingerprint():
    isolation = __import__('finarch.shared.providers.isolation', fromlist=['*'])
    source = inspect.getsource(build_command) + json.dumps(CODEX_DISABLED)
    source += Path(__file__).with_name('policy.py').read_text()
    source += inspect.getsource(isolation.cli_profile)
    source += Path(__file__).with_name("profiles.py").read_text()
    return hashlib.sha256(source.encode()).hexdigest()
