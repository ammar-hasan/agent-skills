# Operating Protocol

Read this reference when supervising an agent beyond a single prompt-and-response exchange.

This protocol is harness-neutral. Tmux pane options and signal channels are the control plane; screen text is an observation fallback.

## State model

Classify the pane from evidence, not appearance alone:

- **Unresolved:** target has not been identified or no longer exists.
- **Idle:** agent is accepting input and has no active tool call.
- **Thinking:** agent is producing reasoning or planning but has not started a costly operation.
- **Executing:** a tool, render, test, build, synthesis, or other subprocess is active.
- **Awaiting input:** the agent asks a question, requests approval, or has a prompt queued but unsubmitted.
- **Complete:** the agent reports completion and returns to input; independent verification is still required.
- **Failed:** the active operation ended with an error.
- **Stalled:** no relevant output or artifact change across multiple bounded observations and no active subprocess explains the delay.

Do not infer `complete` from a blank input area. Do not infer `stalled` from one quiet capture.

For a managed pane, store the committed state in pane-local options:

- `@agent_task_id`, `@agent_state`, `@agent_phase`;
- monotonic `@agent_sequence` and `@agent_updated_at`;
- `@agent_deadline` and `@agent_write_owner`;
- short `@agent_summary` and unique `@agent_signal_channel`.

Update `@agent_sequence` last. A sequence change commits the other option values as one logical state transition.

## Discovery and takeover

1. Run `list`; prefer the user-named target when it exists.
2. Run compact `status` first. Capture at most 80 lines only when identifying an unmanaged pane requires screen evidence. Record the stable pane ID, cwd, current command, harness identity if visible, and task summary.
3. Inspect relevant workspace instructions and artifacts independently.
4. Decide whether to continue the current task, correct it, or replace it. A new user request may amend rather than replace the active assignment.
5. Send a concise takeover assignment through `assign`. Confirm submission once with a changed-screen capture, then observe the pane through `watch`.

If multiple panes plausibly match and choosing incorrectly could alter unrelated work, ask the user to identify the target. Otherwise, use cwd, title, current command, and scrollback to resolve it.

## Assignment template

Adapt this structure; omit irrelevant sections.

```text
OBJECTIVE
<Concrete outcome>

WORKSPACE AND TARGETS
- cwd: <absolute path>
- create/edit: <paths>
- preserve: <paths or existing user changes>

CONSTRAINTS
- <source, product, design, safety, or policy constraints>
- <actions that require approval>

ACCEPTANCE CHECKS
- <observable test or artifact>
- <quality or review gate>

REPORT BACK
- changed files
- commands/checks and exact results
- unresolved risks or required human review
```

Tell the worker to proceed without asking low-value questions when reasonable assumptions are safe. Do not grant authority the user did not grant to the primary agent.

`assign` appends a generic tmux status contract. Do not replace it with harness-specific prompt syntax. Set a realistic deadline and divide long work into independently verifiable stages.

## Writer ownership

Exactly one actor owns writes to the scoped files. The initial assignment sets `@agent_write_owner=worker`. The primary agent may read and verify while the worker owns writes, but must not edit overlapping files. Before takeover, interrupt or finish the worker's atomic action, confirm idle state, change ownership, and then edit. Never rely on two agents resolving concurrent writes correctly.

## Monitoring and signaling

- After sending: recapture promptly to confirm the prompt was submitted rather than merely pasted.
- During ordinary work: use `watch --task-id <id> --since-sequence <n>` repeatedly. Keep the parent turn active until `terminal` is true, the user explicitly requests an asynchronous handoff, or the parent is waiting on a material decision only the user can make.
- A timeout returns compact unchanged state and is not a failure or a stopping condition. Send a concise progress update when appropriate and immediately begin the next bounded watch.
- Send user progress updates as needed without forcing a new capture.
- On `needs_answer`, answer the child and continue the same supervision loop. On a terminal state, a missed deadline, or two consecutive stale observations, capture the changed screen and inspect narrowly.
- After a reported finish: capture the final report once, then perform proportionate independent verification.

Do not end a turn with a promise such as “I’ll keep monitoring.” Once the parent yields, it is no longer running and cannot answer a later child question. If the user explicitly wants background handoff instead of live supervision, state that questions will wait until the parent is invoked again.

Use regex `wait` only for an unmanaged pane that cannot follow the signal contract. Its maximum timeout remains 55 seconds. A normal timeout returns compact JSON; use `--strict-timeout` only when a timeout should be treated as a command failure.

Useful corroboration includes output file timestamps and sizes, a narrowly filtered process listing, test results, render metadata, or a diff. Avoid broad process dumps and large scrollback captures that may reveal secrets.

After two corrections in one stage, stop micromanaging. Re-scope the assignment, transfer ownership, or report the blocker. Do not continue an unbounded send/inspect/interrupt loop.

## Retasking and attribution

Use `assign --replace` when a pane has a different active task. Replacement clears the previous summary and deadline, creates a new signal channel, resets the sequence, commits the new assignment state, and wakes watchers of the previous task with `task_changed: true`. Continue monitoring the new task ID and sequence returned by the helper.

Never edit `@agent_task_id` or another task option in isolation. `signal --force` is only a recovery path for a misattributed child signal; when it changes task identity, it resets stale task-local metadata and reports the previous task ID.

## Answering child questions

An interactive Q/A prompt in the child pane is an input request to the parent supervisor, not automatically a blocker for the user. The assignment contract requires a cooperative child to signal `awaiting-input` with phase `question` and a concise summary before opening its Q/A tool.

When a question appears:

1. Capture the current screen and read the complete question, choices, selected item, and consequences.
2. Answer from explicit user instructions or established task evidence when possible. Otherwise choose a low-risk, reversible default that preserves scope and progress.
3. Ask the user only when no authorized answer can be derived and the choice would materially change intent, grant new authority, expose credentials, spend money, publish externally, destroy data, or create comparable irreversible risk.
4. For a free-text prompt, pipe the answer to `answer`. For a selection UI, pass only the inspected navigation sequence to `answer --keys`; do not assume focus or option order from a prior screen.
5. Capture once after submission. Confirm the Q/A prompt closed and the child resumed, then continue event-driven monitoring.

Do not relay routine implementation questions to the user. Do not answer an approval prompt more broadly than the authority already granted to the primary agent.

## Corrections and interruption

Send a follow-up correction when the worker:

- violates a stated scope or source lock;
- misses an explicit user preference;
- claims success without evidence;
- creates redundant or unsafe artifacts;
- is about to spend significant time or money on a known-bad input;
- repeats an error that the primary agent can resolve.

Let a safe atomic action finish when a queued correction can apply afterward. Interrupt when continuation would materially increase harm, cost, or rework. Before interrupting, capture the pane, identify the active subprocess, preserve any useful saved work, and determine whether that worker expects Escape or Ctrl-C. Use the helper's explicit `--key` choice; never send repeated control keys blindly.

After interruption, confirm the worker is idle, send a clean consolidated correction, and verify it was interpreted as agent input rather than a shell command.

## Verification and handoff

The primary agent owns the final claim. Verify the risky or user-visible parts directly:

- source and scope compliance;
- changed files and preservation of unrelated edits;
- tests, builds, dimensions, durations, or other acceptance metrics;
- visual/audio output when quality is part of the request;
- absence of secrets and unintended external actions.

If a worker cannot inspect a modality that the primary agent can, perform that inspection yourself and correct stale statements in the worker's documentation.

Report whether the pane remains available, was interrupted, or was left idle. Distinguish a review build, draft, or partial result from an approved release.

## Snapshot and restore

An upgrade-safe snapshot must contain every session, window, pane, cwd, layout, and an explicit resume argv for every non-shell pane. Never infer a harness resume command from its executable name. Register the exact argv supplied by that harness or confirmed by the user.

1. Register restore argv for each non-shell pane with `register-restore`.
2. Run `snapshot --require-restorable` to an explicit durable path.
3. Run `restore --input <path>` without `--yes`; require `ready: true`.
4. Confirm managed tasks are idle, complete, or otherwise safe to resume. A snapshot cannot preserve an in-flight subprocess.
5. Keep an external terminal outside the server being restarted so `restore --yes` remains runnable.
6. Upgrade and restart only after explicit approval for the server stop.
7. Run `restore --yes`, verify topology and each harness conversation, renew the signaling contract for any resumed task, then remove the old snapshot only when no longer needed.

## Common failure patterns

- **Prompt pasted but not submitted:** the text remains in the input editor. Send Enter once, then recapture.
- **Child Q/A prompt:** answer it directly when existing instructions or a safe reversible assumption resolve it; otherwise escalate the exact material decision to the user.
- **Parent promised future monitoring after yielding:** resume supervision now and keep the turn alive through bounded watches; a returned parent cannot observe or answer the child.
- **Stale task attribution:** replace the task through `assign --replace`; never patch only the task ID because old summaries, deadlines, and channels will survive.
- **Prompt interpreted as shell input:** stop before expensive work, return to the agent input mode, and resend plain prose without shell-like fragments.
- **Shell-fronted input:** `send` and `assign` refuse it by default. Use `--allow-shell` only when inspection proves a shell-integrated harness currently owns the input surface.
- **Queued correction ignored:** wait for the current atomic action or interrupt if continuation is costly; resend as one consolidated message.
- **Spinner with no evidence:** check the actual child process and artifact timestamps.
- **Unchanged signal wake:** another watcher consumed or left a prior signal; compare `@agent_sequence` and wait again without capturing.
- **Alternate-screen confusion:** capture the currently displayed screen; do not use `capture-pane -a`, which may expose the saved screen behind the TUI.
- **Unrestorable pane:** register an explicit resume argv; do not downgrade the snapshot requirement.
- **Worker declares success too early:** inspect outputs and run the acceptance checks yourself.
- **Agent context drift:** restate only the objective, binding constraints, current evidence, and next required action.
