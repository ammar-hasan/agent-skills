#!/usr/bin/env python3
"""Harness-neutral tmux orchestration, signaling, and session restoration."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

STATE_OPTIONS = {
    "task_id": "@agent_task_id",
    "state": "@agent_state",
    "phase": "@agent_phase",
    "sequence": "@agent_sequence",
    "updated_at": "@agent_updated_at",
    "deadline": "@agent_deadline",
    "summary": "@agent_summary",
    "write_owner": "@agent_write_owner",
    "signal_channel": "@agent_signal_channel",
}

AGENT_STATES = (
    "unmanaged",
    "assigned",
    "working",
    "awaiting-input",
    "verifying",
    "complete",
    "failed",
    "interrupted",
    "restored",
)
TERMINAL_STATES = {"complete", "failed", "interrupted"}
ACTIVE_STATES = {"assigned", "working", "awaiting-input", "verifying", "restored"}

SHELL_COMMANDS = {"bash", "dash", "fish", "ksh", "sh", "tcsh", "zsh"}
ANSWER_KEYS = {
    "up": "Up",
    "down": "Down",
    "left": "Left",
    "right": "Right",
    "tab": "Tab",
    "backtab": "BTab",
    "space": "Space",
    "enter": "Enter",
    "escape": "Escape",
    "page-up": "PPage",
    "page-down": "NPage",
    "home": "Home",
    "end": "End",
}
SNAPSHOT_SCHEMA_VERSION = 1


def run_tmux(args: list[str], *, stdin: str | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["tmux", *args],
            input=stdin,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=check,
        )
    except FileNotFoundError:
        raise SystemExit("tmux is not installed or is not on PATH")
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.strip() or exc.stdout.strip() or "tmux command failed"
        raise SystemExit(detail)


def valid_target(value: str) -> str:
    if not value or any(ord(ch) < 32 for ch in value):
        raise argparse.ArgumentTypeError("target must be non-empty and contain no control characters")
    return value


def ensure_target(target: str) -> str:
    return run_tmux(["display-message", "-p", "-t", target, "#{pane_id}"]).stdout.strip()


def display_format(target: str, fmt: str) -> str:
    return run_tmux(["display-message", "-p", "-t", target, fmt]).stdout.rstrip("\r\n")


def set_pane_option(target: str, option: str, value: str) -> None:
    run_tmux(["set-option", "-p", "-t", target, option, value])


def get_pane_option(target: str, option: str) -> str:
    result = run_tmux(["show-options", "-p", "-q", "-v", "-t", target, option], check=False)
    return result.stdout.rstrip()


def parse_int(value: object, default: int = 0) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def make_signal_channel(pane_id: str, task_id: str) -> str:
    task_digest = hashlib.sha256(task_id.encode("utf-8")).hexdigest()[:16]
    return f"tmux-agent-{pane_id.lstrip('%')}-{task_digest}"


def pane_metadata(target: str) -> dict[str, object]:
    fmt = "\t".join([
        "#{session_name}:#{window_index}.#{pane_index}",
        "#{session_name}",
        "#{window_index}",
        "#{window_name}",
        "#{pane_index}",
        "#{pane_id}",
        "#{pane_active}",
        "#{pane_current_command}",
        "#{pane_current_path}",
        "#{pane_title}",
        "#{pane_dead}",
        "#{alternate_on}",
        "#{pane_pid}",
        "#{pane_start_command}",
    ])
    fields = display_format(target, fmt).split("\t", 13)
    if len(fields) != 14:
        raise SystemExit(f"could not parse tmux metadata for {target}")
    return {
        "target": fields[0],
        "session": fields[1],
        "window_index": parse_int(fields[2]),
        "window_name": fields[3],
        "pane_index": parse_int(fields[4]),
        "pane_id": fields[5],
        "focused": fields[6] == "1",
        "command": fields[7],
        "cwd": fields[8],
        "title": fields[9],
        "dead": fields[10] == "1",
        "alternate_screen": fields[11] == "1",
        "pid": parse_int(fields[12]),
        "start_command": fields[13],
    }


def agent_status(target: str) -> dict[str, object]:
    status = pane_metadata(target)
    pane_id = str(status["pane_id"])
    for key, option in STATE_OPTIONS.items():
        status[key] = get_pane_option(pane_id, option)
    status["sequence"] = parse_int(status["sequence"])
    status["updated_at"] = parse_int(status["updated_at"])
    status["deadline"] = parse_int(status["deadline"])
    if not status["state"]:
        status["state"] = "unmanaged"
    now = int(time.time())
    updated = int(status["updated_at"])
    deadline = int(status["deadline"])
    status["stale_seconds"] = max(0, now - updated) if updated else None
    status["deadline_exceeded"] = bool(deadline and now > deadline)
    status["terminal"] = status["state"] in TERMINAL_STATES
    status["needs_answer"] = status["state"] == "awaiting-input"
    return status


def capture(target: str, lines: int) -> str:
    pane_id = ensure_target(target)
    alternate = display_format(pane_id, "#{alternate_on}") == "1"
    command = ["capture-pane", "-p", "-J", "-t", pane_id]
    # Default capture reads the currently displayed screen, including an active
    # alternate-screen TUI. `capture-pane -a` reads the saved alternate buffer
    # and can therefore return the shell screen behind the TUI.
    if not alternate:
        command.extend(["-S", f"-{lines}"])
    result = run_tmux(command)
    return result.stdout.rstrip()


def screen_result(target: str, lines: int, since_hash: str | None = None) -> dict[str, object]:
    meta = pane_metadata(target)
    content = capture(str(meta["pane_id"]), lines)
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    changed = digest != since_hash if since_hash else True
    return {
        "target": meta["target"],
        "pane_id": meta["pane_id"],
        "alternate_screen": meta["alternate_screen"],
        "screen_hash": digest,
        "changed": changed,
        "content": content if changed else "",
    }


def message_target(target: str, *, allow_shell: bool = False) -> str:
    meta = pane_metadata(target)
    if meta["command"] in SHELL_COMMANDS and not allow_shell:
        raise SystemExit(
            f"refusing to paste agent input into shell-fronted pane {meta['target']}; "
            "confirm a shell-integrated harness with --allow-shell"
        )
    return str(meta["pane_id"])


def send_message(
    target: str,
    message: str,
    *,
    enter: bool = True,
    allow_shell: bool = False,
) -> tuple[str, int]:
    pane_id = message_target(target, allow_shell=allow_shell)
    buffer_name = f"tmux-agent-orchestrator-{os.getpid()}-{time.time_ns()}"
    try:
        run_tmux(["load-buffer", "-b", buffer_name, "-"], stdin=message)
        # Ask tmux to wrap the payload in bracketed-paste control codes when
        # the target application negotiated that terminal capability. This
        # prevents embedded prompt newlines from being submitted separately.
        run_tmux(["paste-buffer", "-d", "-p", "-r", "-b", buffer_name, "-t", pane_id])
    finally:
        run_tmux(["delete-buffer", "-b", buffer_name], check=False)
    if enter:
        run_tmux(["send-keys", "-t", pane_id, "C-m"])
    return pane_id, len(message.encode("utf-8"))


def cmd_list(args: argparse.Namespace) -> None:
    fmt = "#{session_name}\t#{window_index}\t#{pane_index}\t#{pane_id}\t#{pane_active}\t#{pane_current_command}\t#{pane_current_path}\t#{pane_title}\t#{alternate_on}"
    result = run_tmux(["list-panes", "-a", "-F", fmt])
    rows = []
    for line in result.stdout.splitlines():
        fields = line.split("\t", 8)
        if len(fields) != 9:
            continue
        session, window, pane, pane_id, focused, command, cwd, title, alternate = fields
        rows.append({
            "target": f"{session}:{window}.{pane}",
            "pane_id": pane_id,
            "focused": focused == "1",
            "command": command,
            "cwd": cwd,
            "title": title,
            "alternate_screen": alternate == "1",
            "agent_state": get_pane_option(pane_id, STATE_OPTIONS["state"]) or "unmanaged",
            "task_id": get_pane_option(pane_id, STATE_OPTIONS["task_id"]),
        })
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return
    print("TARGET\tPANE\tFOCUSED\tCOMMAND\tSTATE\tCWD\tTITLE")
    for row in rows:
        print(f"{row['target']}\t{row['pane_id']}\t{int(row['focused'])}\t{row['command']}\t{row['agent_state']}\t{row['cwd']}\t{row['title']}")


def cmd_status(args: argparse.Namespace) -> None:
    result = agent_status(args.target)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    print("TASK\tSTATE\tPHASE\tSEQ\tUPDATED\tDEADLINE\tOWNER\tTARGET")
    print(
        f"{result['task_id']}\t{result['state']}\t{result['phase']}\t{result['sequence']}\t"
        f"{result['updated_at']}\t{result['deadline']}\t{result['write_owner']}\t{result['target']}"
    )


def cmd_capture(args: argparse.Namespace) -> None:
    result = screen_result(args.target, args.lines, args.since_hash)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif result["changed"]:
        print(result["content"])


def cmd_inspect(args: argparse.Namespace) -> None:
    status = agent_status(args.target)
    if args.compact:
        if args.json:
            print(json.dumps(status, ensure_ascii=False, indent=2))
        else:
            print(
                f"{status['target']} pane={status['pane_id']} command={status['command']} "
                f"state={status['state']} phase={status['phase']} seq={status['sequence']} "
                f"alternate={int(bool(status['alternate_screen']))} cwd={status['cwd']}"
            )
        return
    screen = screen_result(args.target, args.lines, args.since_hash)
    if args.json:
        print(json.dumps({"status": status, "screen": screen}, ensure_ascii=False, indent=2))
        return
    print("TARGET\tPANE\tFOCUSED\tCOMMAND\tSTATE\tCWD\tTITLE\tDEAD")
    print(
        f"{status['target']}\t{status['pane_id']}\t{int(bool(status['focused']))}\t{status['command']}\t"
        f"{status['state']}\t{status['cwd']}\t{status['title']}\t{int(bool(status['dead']))}"
    )
    print("\n--- CAPTURE ---")
    if screen["changed"]:
        print(screen["content"])
    else:
        print(f"unchanged screen {screen['screen_hash']}")


def cmd_send(args: argparse.Namespace) -> None:
    if sys.stdin.isatty():
        raise SystemExit("no message provided; pipe content on stdin")
    message = sys.stdin.read()
    if not message:
        raise SystemExit("no message provided; pipe content on stdin")
    pane_id, size = send_message(
        args.target,
        message,
        enter=not args.no_enter,
        allow_shell=args.allow_shell,
    )
    suffix = " without Enter" if args.no_enter else ""
    print(f"sent {size} bytes to {pane_id}{suffix}")


def cmd_answer(args: argparse.Namespace) -> None:
    pane_id = message_target(args.target, allow_shell=args.allow_shell)
    if args.keys:
        if args.no_enter:
            raise SystemExit("--no-enter applies only to a text answer")
        tmux_keys = [ANSWER_KEYS[key] for key in args.keys]
        run_tmux(["send-keys", "-t", pane_id, *tmux_keys])
        print(json.dumps({
            "target": pane_id,
            "mode": "keys",
            "keys": args.keys,
        }, ensure_ascii=False, indent=2))
        return
    if sys.stdin.isatty():
        raise SystemExit("no answer provided; pipe text on stdin or use --keys")
    answer = sys.stdin.read().rstrip("\r\n")
    if not answer:
        raise SystemExit("no answer provided; pipe text on stdin or use --keys")
    pane_id, size = send_message(
        pane_id,
        answer,
        enter=not args.no_enter,
        allow_shell=args.allow_shell,
    )
    print(json.dumps({
        "target": pane_id,
        "mode": "text",
        "bytes_sent": size,
        "submitted": not args.no_enter,
    }, ensure_ascii=False, indent=2))


def cmd_assign(args: argparse.Namespace) -> None:
    if sys.stdin.isatty():
        raise SystemExit("no assignment provided; pipe the assignment on stdin")
    assignment = sys.stdin.read()
    if not assignment:
        raise SystemExit("no assignment provided; pipe the assignment on stdin")
    pane_id = message_target(args.target, allow_shell=args.allow_shell)
    task_id = args.task_id or uuid.uuid4().hex
    current = agent_status(pane_id)
    current_task = str(current["task_id"])
    replacing = bool(current_task and current_task != task_id)
    if replacing and current["state"] in ACTIVE_STATES and not args.replace:
        raise SystemExit(
            f"pane {pane_id} has active task {current_task}; use --replace to retask it"
        )
    previous_channel = str(current["signal_channel"]) if replacing else ""
    now = int(time.time())
    deadline = now + max(1, int(args.deadline_minutes * 60)) if args.deadline_minutes else 0
    channel = make_signal_channel(pane_id, task_id)
    initial = {
        "task_id": task_id,
        "state": "assigned",
        "phase": "assignment",
        "sequence": "0",
        "updated_at": str(now),
        "deadline": str(deadline),
        "summary": "",
        "write_owner": "worker",
        "signal_channel": channel,
    }
    for key, value in initial.items():
        if key == "sequence":
            continue
        set_pane_option(pane_id, STATE_OPTIONS[key], value)
    # Sequence commits the complete replacement state for new observers.
    set_pane_option(pane_id, STATE_OPTIONS["sequence"], initial["sequence"])
    helper = str(Path(__file__).resolve())
    quoted_helper = shlex.quote(helper)
    quoted_task_id = shlex.quote(task_id)
    contract = f"""

TMUX STATUS CONTRACT (required)
- Task id: {task_id}; exact pane: {pane_id}.
- Before substantive work, run:
  python3 {quoted_helper} signal --target {pane_id} --task-id {quoted_task_id} --state working --phase execution
- Signal again at meaningful checkpoints, changing --phase to a short stable label.
- Before opening an interactive Q/A tool, signal state awaiting-input with phase question and put the concise question and choices in --summary.
- After the parent answers the Q/A prompt, signal working before resuming execution.
- Use your own judgment for low-risk decisions; the parent supervisor answers Q/A prompts and escalates only materially new choices or authority.
- After saving work and preparing the final report, signal complete; on unrecoverable failure, signal failed.
- Do not edit while the pane option @agent_write_owner is not worker.
"""
    _, size = send_message(
        pane_id,
        assignment.rstrip() + contract,
        enter=not args.no_enter,
        allow_shell=args.allow_shell,
    )
    if previous_channel:
        run_tmux(["wait-for", "-S", previous_channel])
    result = agent_status(pane_id)
    result["bytes_sent"] = size
    result["task_changed"] = replacing
    result["previous_task_id"] = current_task if replacing else ""
    print(json.dumps(result, ensure_ascii=False, indent=2))


def update_agent_state(args: argparse.Namespace) -> dict[str, object]:
    pane_id = ensure_target(args.target)
    current_task = get_pane_option(pane_id, STATE_OPTIONS["task_id"])
    replacing = bool(current_task and current_task != args.task_id)
    if replacing and not args.force:
        raise SystemExit(f"task mismatch for {pane_id}: current task is {current_task}")
    previous_channel = get_pane_option(pane_id, STATE_OPTIONS["signal_channel"])
    sequence = 1 if replacing else parse_int(get_pane_option(pane_id, STATE_OPTIONS["sequence"])) + 1
    set_pane_option(pane_id, STATE_OPTIONS["task_id"], args.task_id)
    set_pane_option(pane_id, STATE_OPTIONS["state"], args.state)
    set_pane_option(pane_id, STATE_OPTIONS["phase"], args.phase)
    if args.summary is not None:
        set_pane_option(pane_id, STATE_OPTIONS["summary"], args.summary)
    elif replacing:
        set_pane_option(pane_id, STATE_OPTIONS["summary"], "")
    if replacing:
        set_pane_option(pane_id, STATE_OPTIONS["deadline"], "0")
        set_pane_option(
            pane_id,
            STATE_OPTIONS["signal_channel"],
            make_signal_channel(pane_id, args.task_id),
        )
    if args.write_owner is not None:
        set_pane_option(pane_id, STATE_OPTIONS["write_owner"], args.write_owner)
    set_pane_option(pane_id, STATE_OPTIONS["updated_at"], str(int(time.time())))
    # Sequence is deliberately last: it commits the state change for subscribers.
    set_pane_option(pane_id, STATE_OPTIONS["sequence"], str(sequence))
    channel = get_pane_option(pane_id, STATE_OPTIONS["signal_channel"])
    if not args.no_notify:
        for notification_channel in dict.fromkeys((previous_channel, channel)):
            if notification_channel:
                run_tmux(["wait-for", "-S", notification_channel])
    result = agent_status(pane_id)
    result.update({
        "changed": True,
        "timed_out": False,
        "task_changed": replacing,
        "previous_task_id": current_task if replacing else "",
    })
    return result


def cmd_signal(args: argparse.Namespace) -> None:
    print(json.dumps(update_agent_state(args), ensure_ascii=False, indent=2))


def cmd_watch(args: argparse.Namespace) -> None:
    initial = agent_status(args.target)
    if args.task_id and initial["task_id"] != args.task_id:
        initial.update({
            "changed": True,
            "timed_out": False,
            "task_changed": True,
            "previous_task_id": args.task_id,
        })
        print(json.dumps(initial, ensure_ascii=False, indent=2))
        return
    if int(initial["sequence"]) > args.since_sequence:
        initial.update({"changed": True, "timed_out": False})
        print(json.dumps(initial, ensure_ascii=False, indent=2))
        return
    channel = str(initial["signal_channel"])
    if not channel:
        raise SystemExit("pane has no signal channel; use assign first")
    deadline = time.monotonic() + args.timeout
    spurious_wakes = 0
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        try:
            subprocess.run(
                ["tmux", "wait-for", channel],
                text=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                check=True,
                timeout=remaining,
            )
        except subprocess.TimeoutExpired:
            break
        except subprocess.CalledProcessError as exc:
            raise SystemExit(exc.stderr.strip() or "tmux wait-for failed")
        result = agent_status(args.target)
        if args.task_id and result["task_id"] != args.task_id:
            result.update({
                "changed": True,
                "timed_out": False,
                "task_changed": True,
                "previous_task_id": args.task_id,
                "spurious_wakes": spurious_wakes,
            })
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return
        if int(result["sequence"]) > args.since_sequence:
            result.update({"changed": True, "timed_out": False, "spurious_wakes": spurious_wakes})
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return
        # A signal can remain available after another observer returned from
        # its pre-wait sequence check. Consume it without treating it as work.
        spurious_wakes += 1
    result = agent_status(args.target)
    if args.task_id and result["task_id"] != args.task_id:
        result.update({
            "changed": True,
            "timed_out": False,
            "task_changed": True,
            "previous_task_id": args.task_id,
            "spurious_wakes": spurious_wakes,
        })
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    changed = int(result["sequence"]) > args.since_sequence
    result.update({"changed": changed, "timed_out": not changed, "spurious_wakes": spurious_wakes})
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["timed_out"] and args.strict_timeout:
        raise SystemExit(2)


def cmd_wait(args: argparse.Namespace) -> None:
    # Compatibility fallback for unmanaged panes. Managed panes should use watch.
    try:
        pattern = re.compile(args.pattern, re.IGNORECASE | re.MULTILINE)
    except re.error as exc:
        raise SystemExit(f"invalid regex: {exc}")
    baseline = capture(args.target, args.lines)
    baseline_matches = sum(1 for _ in pattern.finditer(baseline))
    deadline = time.monotonic() + args.timeout
    latest = baseline
    matched = False
    while True:
        latest = capture(args.target, args.lines)
        current_matches = sum(1 for _ in pattern.finditer(latest))
        if current_matches > baseline_matches:
            matched = True
            break
        if time.monotonic() >= deadline:
            break
        time.sleep(args.interval)
    digest = hashlib.sha256(latest.encode("utf-8")).hexdigest()
    tail = latest.splitlines()[-args.tail_lines:] if args.tail_lines else []
    print(json.dumps({
        "matched": matched,
        "timed_out": not matched,
        "screen_hash": digest,
        "tail": tail,
    }, ensure_ascii=False, indent=2))
    if not matched and args.strict_timeout:
        raise SystemExit(2)


def cmd_interrupt(args: argparse.Namespace) -> None:
    if not args.yes:
        raise SystemExit("refusing to interrupt without --yes")
    ensure_target(args.target)
    tmux_key = {"escape": "Escape", "ctrl-c": "C-c"}[args.key]
    for index in range(args.count):
        run_tmux(["send-keys", "-t", args.target, tmux_key])
        if index + 1 < args.count:
            time.sleep(args.delay)
    print(f"sent {args.key} x{args.count} to {args.target}")


def cmd_launch(args: argparse.Namespace) -> None:
    cwd = Path(args.cwd).expanduser().resolve()
    if not cwd.is_dir():
        raise SystemExit(f"working directory does not exist: {cwd}")
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        raise SystemExit("provide the agent command after --")
    run_tmux(["has-session", "-t", args.session])
    shell_command = shlex.join(command)
    fmt = "#{session_name}:#{window_index}.#{pane_index}\t#{pane_id}\t#{pane_current_path}\t#{pane_current_command}"
    result = run_tmux([
        "new-window", "-d", "-P", "-F", fmt,
        "-t", f"{args.session}:", "-n", args.name, "-c", str(cwd), shell_command,
    ])
    pane_id = result.stdout.rstrip().split("\t")[1]
    # A command that launches a harness is not necessarily a command that
    # resumes its conversation. Require an explicit register-restore call.
    set_pane_option(pane_id, "@agent_restore_cwd", str(cwd))
    print(result.stdout.rstrip())


def cmd_register_restore(args: argparse.Namespace) -> None:
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        raise SystemExit("provide the exact resume command after --")
    meta = pane_metadata(args.target)
    cwd = str(Path(args.cwd).expanduser().resolve()) if args.cwd else str(meta["cwd"])
    if not Path(cwd).is_dir():
        raise SystemExit(f"restore working directory does not exist: {cwd}")
    pane_id = str(meta["pane_id"])
    set_pane_option(pane_id, "@agent_restore_argv", json.dumps(command, ensure_ascii=False))
    set_pane_option(pane_id, "@agent_restore_cwd", cwd)
    print(json.dumps({"pane_id": pane_id, "cwd": cwd, "argv": command}, ensure_ascii=False, indent=2))


def restore_argv_for(pane_id: str, current_command: str, default_shell: str) -> tuple[list[str] | None, str]:
    raw = get_pane_option(pane_id, "@agent_restore_argv")
    if raw:
        try:
            argv = json.loads(raw)
        except json.JSONDecodeError:
            return None, "invalid @agent_restore_argv"
        if isinstance(argv, list) and argv and all(isinstance(value, str) for value in argv):
            return argv, "registered"
        return None, "invalid @agent_restore_argv"
    if current_command in SHELL_COMMANDS:
        return [default_shell, "-l"], "shell"
    return None, "explicit resume command required"


def collect_snapshot(session_filter: str | None = None) -> dict[str, object]:
    version = run_tmux(["display-message", "-p", "#{version}"]).stdout.strip()
    default_shell = run_tmux(["show-options", "-g", "-v", "default-shell"]).stdout.strip() or "/bin/sh"
    session_fmt = "#{session_name}\t#{session_windows}\t#{session_attached}\t#{session_created}\t#{session_group}"
    window_fmt = "#{session_name}\t#{window_index}\t#{window_name}\t#{window_active}\t#{window_layout}\t#{window_panes}"
    pane_fmt = "#{session_name}\t#{window_index}\t#{pane_index}\t#{pane_id}\t#{pane_active}\t#{pane_current_command}\t#{pane_current_path}\t#{pane_title}\t#{pane_dead}\t#{pane_start_command}"
    sessions: list[dict[str, object]] = []
    for line in run_tmux(["list-sessions", "-F", session_fmt]).stdout.splitlines():
        fields = line.split("\t", 4)
        if session_filter and fields[0] != session_filter:
            continue
        sessions.append({
            "name": fields[0],
            "windows": parse_int(fields[1]),
            "attached": parse_int(fields[2]),
            "created": parse_int(fields[3]),
            "group": fields[4],
        })
    windows: list[dict[str, object]] = []
    for line in run_tmux(["list-windows", "-a", "-F", window_fmt]).stdout.splitlines():
        fields = line.split("\t", 5)
        if session_filter and fields[0] != session_filter:
            continue
        windows.append({
            "session": fields[0],
            "index": parse_int(fields[1]),
            "name": fields[2],
            "active": fields[3] == "1",
            "layout": fields[4],
            "pane_count": parse_int(fields[5]),
        })
    option_names = list(STATE_OPTIONS.values()) + ["@agent_restore_argv", "@agent_restore_cwd"]
    panes: list[dict[str, object]] = []
    for line in run_tmux(["list-panes", "-a", "-F", pane_fmt]).stdout.splitlines():
        fields = line.split("\t", 9)
        if session_filter and fields[0] != session_filter:
            continue
        pane_id = fields[3]
        restore_argv, restore_source = restore_argv_for(pane_id, fields[5], default_shell)
        options = {name: get_pane_option(pane_id, name) for name in option_names}
        cwd = options["@agent_restore_cwd"] or fields[6]
        panes.append({
            "session": fields[0],
            "window_index": parse_int(fields[1]),
            "pane_index": parse_int(fields[2]),
            "pane_id": pane_id,
            "active": fields[4] == "1",
            "current_command": fields[5],
            "cwd": cwd,
            "title": fields[7],
            "dead": fields[8] == "1",
            "start_command": fields[9],
            "restore_argv": restore_argv,
            "restore_source": restore_source,
            "restorable": restore_argv is not None,
            "agent_options": options,
        })
    return {
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "created_at": int(time.time()),
        "tmux_version": version,
        "default_shell": default_shell,
        "sessions": sessions,
        "windows": windows,
        "panes": panes,
    }


def atomic_write_json(path: Path, payload: dict[str, object]) -> None:
    if not path.parent.is_dir():
        raise SystemExit(f"output parent directory does not exist: {path.parent}")
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        temporary = Path(handle.name)
    os.replace(temporary, path)


def cmd_snapshot(args: argparse.Namespace) -> None:
    if args.session:
        run_tmux(["has-session", "-t", args.session])
    snapshot = collect_snapshot(args.session)
    panes = snapshot["panes"]
    assert isinstance(panes, list)
    unrestorable = [pane for pane in panes if not pane["restorable"]]
    if args.require_restorable and unrestorable:
        details = ", ".join(
            f"{pane['session']}:{pane['window_index']}.{pane['pane_index']} ({pane['current_command']})"
            for pane in unrestorable
        )
        raise SystemExit(f"refusing snapshot: panes need explicit restore commands: {details}")
    output = Path(args.output).expanduser().resolve()
    atomic_write_json(output, snapshot)
    print(json.dumps({
        "output": str(output),
        "sessions": len(snapshot["sessions"]),
        "windows": len(snapshot["windows"]),
        "panes": len(panes),
        "unrestorable": len(unrestorable),
    }, indent=2))


def load_snapshot(path_value: str) -> dict[str, object]:
    path = Path(path_value).expanduser().resolve()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"could not read snapshot {path}: {exc}")
    if payload.get("schema_version") != SNAPSHOT_SCHEMA_VERSION:
        raise SystemExit(f"unsupported snapshot schema: {payload.get('schema_version')}")
    return payload


def make_restore_plan(snapshot: dict[str, object]) -> dict[str, object]:
    panes = snapshot["panes"]
    sessions = snapshot["sessions"]
    windows = snapshot["windows"]
    assert isinstance(panes, list) and isinstance(sessions, list) and isinstance(windows, list)
    unrestorable = [pane for pane in panes if not pane.get("restorable")]
    issues: list[str] = []
    for pane in panes:
        target = f"{pane['session']}:{pane['window_index']}.{pane['pane_index']}"
        cwd = Path(str(pane.get("cwd", "")))
        if not cwd.is_dir():
            issues.append(f"{target}: working directory does not exist: {cwd}")
        argv = pane.get("restore_argv")
        if isinstance(argv, list) and argv:
            executable = str(argv[0])
            if not (Path(executable).is_file() if Path(executable).is_absolute() else shutil.which(executable)):
                issues.append(f"{target}: restore executable is unavailable: {executable}")
    return {
        "source_tmux_version": snapshot.get("tmux_version"),
        "sessions": [session["name"] for session in sessions],
        "window_count": len(windows),
        "pane_count": len(panes),
        "unrestorable": [
            f"{pane['session']}:{pane['window_index']}.{pane['pane_index']} ({pane['current_command']})"
            for pane in unrestorable
        ],
        "issues": issues,
        "ready": not unrestorable and not issues,
    }


def restore_command_string(pane: dict[str, object]) -> str:
    argv = pane.get("restore_argv")
    if not isinstance(argv, list) or not argv:
        raise SystemExit(f"pane {pane.get('pane_id')} has no restore command")
    return shlex.join(str(value) for value in argv)


def restore_pane_options(new_pane: str, pane: dict[str, object]) -> None:
    options = pane.get("agent_options") or {}
    assert isinstance(options, dict)
    excluded = {
        STATE_OPTIONS["signal_channel"],
        STATE_OPTIONS["state"],
        STATE_OPTIONS["phase"],
        STATE_OPTIONS["sequence"],
        STATE_OPTIONS["updated_at"],
    }
    for name, value in options.items():
        if value and name not in excluded:
            set_pane_option(new_pane, str(name), str(value))
    task_id = str(options.get(STATE_OPTIONS["task_id"], ""))
    if task_id:
        sequence = parse_int(options.get(STATE_OPTIONS["sequence"])) + 1
        set_pane_option(new_pane, STATE_OPTIONS["signal_channel"], make_signal_channel(new_pane, task_id))
        set_pane_option(new_pane, STATE_OPTIONS["state"], "restored")
        set_pane_option(new_pane, STATE_OPTIONS["phase"], "session-restored")
        set_pane_option(new_pane, STATE_OPTIONS["updated_at"], str(int(time.time())))
        set_pane_option(new_pane, STATE_OPTIONS["sequence"], str(sequence))


def cmd_restore(args: argparse.Namespace) -> None:
    snapshot = load_snapshot(args.input)
    plan = make_restore_plan(snapshot)
    if not args.yes:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return
    if not plan["ready"]:
        raise SystemExit("refusing restore: snapshot contains unrestorable or unavailable panes")
    existing_result = run_tmux(["list-sessions", "-F", "#{session_name}"], check=False)
    existing = {line.strip() for line in existing_result.stdout.splitlines()}
    conflicts = existing.intersection(plan["sessions"])
    if conflicts:
        raise SystemExit(f"refusing restore because sessions already exist: {', '.join(sorted(conflicts))}")

    sessions = snapshot["sessions"]
    windows = snapshot["windows"]
    panes = snapshot["panes"]
    assert isinstance(sessions, list) and isinstance(windows, list) and isinstance(panes, list)
    restored: dict[tuple[str, int, int], str] = {}
    for session in sessions:
        session_name = str(session["name"])
        session_windows = sorted(
            (window for window in windows if window["session"] == session_name),
            key=lambda value: value["index"],
        )
        for window_number, window in enumerate(session_windows):
            window_panes = sorted(
                (pane for pane in panes if pane["session"] == session_name and pane["window_index"] == window["index"]),
                key=lambda value: value["pane_index"],
            )
            first = window_panes[0]
            if window_number == 0:
                created = run_tmux([
                    "new-session", "-d", "-P", "-F", "#{window_index}\t#{pane_id}",
                    "-s", session_name, "-n", str(window["name"]), "-c", str(first["cwd"]),
                    restore_command_string(first),
                ]).stdout.rstrip().split("\t")
                actual_index, first_pane = parse_int(created[0]), created[1]
                if actual_index != window["index"]:
                    run_tmux(["move-window", "-s", f"{session_name}:{actual_index}", "-t", f"{session_name}:{window['index']}"])
            else:
                first_pane = run_tmux([
                    "new-window", "-d", "-P", "-F", "#{pane_id}",
                    "-t", f"{session_name}:{window['index']}", "-n", str(window["name"]),
                    "-c", str(first["cwd"]), restore_command_string(first),
                ]).stdout.strip()
            restored[(session_name, int(window["index"]), int(first["pane_index"]))] = first_pane
            for pane in window_panes[1:]:
                new_pane = run_tmux([
                    "split-window", "-d", "-P", "-F", "#{pane_id}",
                    "-t", f"{session_name}:{window['index']}", "-c", str(pane["cwd"]),
                    restore_command_string(pane),
                ]).stdout.strip()
                restored[(session_name, int(window["index"]), int(pane["pane_index"]))] = new_pane
            if window.get("layout"):
                run_tmux(["select-layout", "-t", f"{session_name}:{window['index']}", str(window["layout"])])
            for pane in window_panes:
                new_pane = restored[(session_name, int(window["index"]), int(pane["pane_index"]))]
                if pane.get("title"):
                    run_tmux(["select-pane", "-t", new_pane, "-T", str(pane["title"])])
                restore_pane_options(new_pane, pane)
                if pane.get("active"):
                    run_tmux(["select-pane", "-t", new_pane])
            if window.get("active"):
                run_tmux(["select-window", "-t", f"{session_name}:{window['index']}"])
    print(json.dumps({"restored_sessions": plan["sessions"], "restored_panes": len(restored)}, indent=2))


def bounded_int(minimum: int, maximum: int):
    def parse(value: str) -> int:
        number = int(value)
        if not minimum <= number <= maximum:
            raise argparse.ArgumentTypeError(f"must be between {minimum} and {maximum}")
        return number
    return parse


def positive_float(value: str) -> float:
    number = float(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("must be positive")
    return number


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command_name", required=True)

    p_list = sub.add_parser("list", help="list every tmux pane with agent-relevant metadata")
    p_list.add_argument("--json", action="store_true")
    p_list.set_defaults(func=cmd_list)

    p_status = sub.add_parser("status", help="show compact pane state without capturing the screen")
    p_status.add_argument("--target", required=True, type=valid_target)
    p_status.add_argument("--json", action="store_true")
    p_status.set_defaults(func=cmd_status)

    p_capture = sub.add_parser("capture", help="capture the active screen or scrollback with change detection")
    p_capture.add_argument("--target", required=True, type=valid_target)
    p_capture.add_argument("--lines", type=bounded_int(1, 5000), default=80)
    p_capture.add_argument("--since-hash")
    p_capture.add_argument("--json", action="store_true")
    p_capture.set_defaults(func=cmd_capture)

    p_inspect = sub.add_parser("inspect", help="show pane metadata and an optional changed screen")
    p_inspect.add_argument("--target", required=True, type=valid_target)
    p_inspect.add_argument("--lines", type=bounded_int(1, 5000), default=80)
    p_inspect.add_argument("--since-hash")
    p_inspect.add_argument("--compact", action="store_true")
    p_inspect.add_argument("--json", action="store_true")
    p_inspect.set_defaults(func=cmd_inspect)

    p_send = sub.add_parser("send", help="paste a literal message safely and optionally press Enter")
    p_send.add_argument("--target", required=True, type=valid_target)
    p_send.add_argument("--no-enter", action="store_true")
    p_send.add_argument(
        "--allow-shell",
        action="store_true",
        help="confirm that a shell-fronted pane is currently an agent input surface",
    )
    p_send.set_defaults(func=cmd_send)

    p_answer = sub.add_parser(
        "answer", help="answer a child Q/A prompt with text or explicit navigation keys"
    )
    p_answer.add_argument("--target", required=True, type=valid_target)
    p_answer.add_argument("--keys", nargs="+", choices=tuple(ANSWER_KEYS))
    p_answer.add_argument("--no-enter", action="store_true")
    p_answer.add_argument(
        "--allow-shell",
        action="store_true",
        help="confirm that a shell-fronted pane is currently an agent input surface",
    )
    p_answer.set_defaults(func=cmd_answer)

    p_assign = sub.add_parser(
        "assign", help="initialize or explicitly replace task state and send its contract"
    )
    p_assign.add_argument("--target", required=True, type=valid_target)
    p_assign.add_argument("--task-id")
    p_assign.add_argument("--deadline-minutes", type=positive_float)
    p_assign.add_argument(
        "--replace",
        action="store_true",
        help="explicitly replace a different active task and reset its state",
    )
    p_assign.add_argument("--no-enter", action="store_true")
    p_assign.add_argument(
        "--allow-shell",
        action="store_true",
        help="confirm that a shell-fronted pane is currently an agent input surface",
    )
    p_assign.set_defaults(func=cmd_assign)

    p_signal = sub.add_parser("signal", help="commit pane state and wake the tmux signal channel")
    p_signal.add_argument("--target", required=True, type=valid_target)
    p_signal.add_argument("--task-id", required=True)
    p_signal.add_argument("--state", required=True, choices=AGENT_STATES)
    p_signal.add_argument("--phase", required=True)
    p_signal.add_argument("--summary")
    p_signal.add_argument("--write-owner", choices=("worker", "primary", "none"))
    p_signal.add_argument(
        "--force",
        action="store_true",
        help="repair a mismatched task signal and reset stale task-local metadata",
    )
    p_signal.add_argument("--no-notify", action="store_true")
    p_signal.set_defaults(func=cmd_signal)

    p_watch = sub.add_parser("watch", help="wait on a tmux channel and return compact structured state")
    p_watch.add_argument("--target", required=True, type=valid_target)
    p_watch.add_argument("--task-id")
    p_watch.add_argument("--since-sequence", type=bounded_int(0, 1_000_000_000), default=0)
    p_watch.add_argument("--timeout", type=bounded_int(1, 55), default=45)
    p_watch.add_argument("--strict-timeout", action="store_true")
    p_watch.set_defaults(func=cmd_watch)

    p_wait = sub.add_parser("wait", help="compatibility regex wait for unmanaged panes; prefer watch")
    p_wait.add_argument("--target", required=True, type=valid_target)
    p_wait.add_argument("--pattern", required=True)
    p_wait.add_argument("--timeout", type=bounded_int(1, 55), default=30)
    p_wait.add_argument("--interval", type=positive_float, default=2.0)
    p_wait.add_argument("--lines", type=bounded_int(1, 5000), default=80)
    p_wait.add_argument("--tail-lines", type=bounded_int(0, 100), default=12)
    p_wait.add_argument("--strict-timeout", action="store_true")
    p_wait.set_defaults(func=cmd_wait)

    p_interrupt = sub.add_parser("interrupt", help="send one or two deliberate cancellation keys")
    p_interrupt.add_argument("--target", required=True, type=valid_target)
    p_interrupt.add_argument("--key", choices=("escape", "ctrl-c"), required=True)
    p_interrupt.add_argument("--count", type=bounded_int(1, 2), default=1)
    p_interrupt.add_argument("--delay", type=positive_float, default=1.0)
    p_interrupt.add_argument("--yes", action="store_true")
    p_interrupt.set_defaults(func=cmd_interrupt)

    p_launch = sub.add_parser("launch", help="create a detached tmux window for an explicitly chosen agent command")
    p_launch.add_argument("--session", required=True, type=valid_target)
    p_launch.add_argument("--name", required=True)
    p_launch.add_argument("--cwd", required=True)
    p_launch.add_argument("command", nargs=argparse.REMAINDER)
    p_launch.set_defaults(func=cmd_launch)

    p_register = sub.add_parser("register-restore", help="register an exact harness resume command")
    p_register.add_argument("--target", required=True, type=valid_target)
    p_register.add_argument("--cwd")
    p_register.add_argument("command", nargs=argparse.REMAINDER)
    p_register.set_defaults(func=cmd_register_restore)

    p_snapshot = sub.add_parser("snapshot", help="write topology and explicitly registered resume commands")
    p_snapshot.add_argument("--output", required=True)
    p_snapshot.add_argument("--session", type=valid_target)
    p_snapshot.add_argument("--require-restorable", action="store_true")
    p_snapshot.set_defaults(func=cmd_snapshot)

    p_restore = sub.add_parser("restore", help="dry-run or restore sessions from a snapshot")
    p_restore.add_argument("--input", required=True)
    p_restore.add_argument("--yes", action="store_true", help="perform restore; otherwise print the plan")
    p_restore.set_defaults(func=cmd_restore)

    return parser


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
