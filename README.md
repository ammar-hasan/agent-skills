<div align="center">

# Agent Skills

**Good workflows. Shared as skills.**

A curated collection of practical skills for AI agents, maintained by [Ammar Hasan](https://github.com/ammar-hasan).

[Public catalog](https://ammar-hasan.github.io/agent-skills/) · [Browse the skills](#the-catalog) · [Install a skill](#get-started) · [Contribute](CONTRIBUTING.md) · [MIT license](LICENSE)

</div>

These skills capture the instructions, tools, and working habits that make an agent useful on a particular task. Each one lives in its own folder, so you can read it, install it, and adapt it independently.

This collection grows deliberately. Skills are added when we choose to promote them here; a skill being installed on a maintainer’s machine does not make it part of this repository.

## Get started

Install the tmux skill with the [skills CLI](https://github.com/vercel-labs/skills):

```sh
npx skills add ammar-hasan/agent-skills --skill tmux-agent-orchestrator
```

The installer lets you choose your agent. Add `--global` if you want the skill available across projects.

To see what is available without installing anything:

```sh
npx skills add ammar-hasan/agent-skills --list
```

For a reproducible installation of the **1.0.0** release:

```sh
npx skills add https://github.com/ammar-hasan/agent-skills/tree/tmux-agent-orchestrator-v1.0.0/skills/tmux-agent-orchestrator --global
```

The short repository command follows `main`; the release URL selects the tagged version. Each skill has its own version in `SKILL.md`, changelog, and release tag. See [versioning and releases](CONTRIBUTING.md#versioning-and-releases) for the policy. Website-only changes do not change skill versions.

Prefer a manual installation? Copy the entire folder from `skills/` into your agent’s supported skills directory. Keep its scripts and references alongside `SKILL.md`.

## The catalog

| Skill | What it helps with | Requirements |
| --- | --- | --- |
| [osw](skills/osw/SKILL.md) | Manually invoke `$osw` to answer in one line using simple words, or simplify the last answer when no arguments are provided. | No extra tools. |
| [sdo](skills/sdo/SKILL.md) | Manually invoke `$sdo` to answer with a simple diagram only, or turn the last answer into a diagram when no arguments are provided. | No extra tools. |
| [sto](skills/sto/SKILL.md) | Manually invoke `$sto` to answer with a simple table only, or turn the last answer into a table when no arguments are provided. | No extra tools. |
| [Tmux Agent Orchestrator](skills/tmux-agent-orchestrator/SKILL.md) | Direct and monitor an interactive AI agent running in tmux, handle questions, track progress, and verify the result. | tmux, Python 3.9+, and an agent that can run shell commands. |

### Tmux Agent Orchestrator

Use this when an agent is already working in a tmux pane and you want your primary agent to supervise it. It can also help launch an agent when you request that, or prepare a restorable session before a restart.

Try a request like:

> Use tmux-agent-orchestrator to find the agent working on this project, check its progress, and supervise it until the task is complete. Verify the result before reporting back.

The skill gives the primary agent a concrete protocol for assigning work, observing state changes, answering questions, and intervening when needed. Its Python helper uses tmux itself for state and signaling. It has no Python package dependencies or vendor-specific API requirement.

You still need to install and configure the agent you want to supervise. Session snapshots record topology and registered resume commands; restoring a conversation depends on that agent’s own resume support. This skill is for supervising agents, rather than general tmux administration.

Read the [skill instructions](skills/tmux-agent-orchestrator/SKILL.md) or the [operating protocol](skills/tmux-agent-orchestrator/references/operating-protocol.md) for details.

## Built to travel

Skills follow the [Agent Skills format](https://agentskills.io/specification): a folder with a `SKILL.md` entrypoint, YAML metadata, and any supporting resources. The `skills/<skill-name>/` layout is discoverable by the [skills.sh CLI](https://github.com/vercel-labs/skills) and other tools that support this convention.

Format compatibility does not remove a skill’s runtime requirements. Check the catalog and the skill itself before installing. Listing on a third-party directory is managed by that directory; this repository does not imply an endorsement or a guaranteed listing.

## Repository layout

```text
skills/
  osw/
    SKILL.md                 # One simple instruction
    LICENSE
    CHANGELOG.md
  sdo/                       # Simple diagram only; manually invoked
  sto/                       # Simple table only; manually invoked
  tmux-agent-orchestrator/
    SKILL.md                 # Instructions and discovery metadata
    LICENSE                  # License travels with the installed skill
    CHANGELOG.md             # Versioned changes for this skill
    agents/openai.yaml       # Optional agent UI metadata
    scripts/                 # Runtime helper
    references/              # Detailed operating protocol
    tests/                   # Helper integration tests
site/                        # Public catalog website
scripts/                     # Repository validation
.github/workflows/           # Automated checks
```

The website is separate from the installable skills. You do not need to build it to use them.

## Developing and contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for the promotion process and local checks. Focused fixes and useful examples are welcome. New skills should solve a clear, repeatable problem and be selected for inclusion by a maintainer.

## License

[MIT](LICENSE). Use, adapt, and share these skills, keeping the license notice with your copy.
