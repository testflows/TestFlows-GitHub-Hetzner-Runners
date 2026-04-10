# AGENTS.md — GitHub Hetzner Runners

Reference for AI agents working in this codebase. Covers architecture, conventions, and design decisions relevant to ongoing development.

---

## What This Project Does

`github-hetzner-runners` is a self-hosted GitHub Actions autoscaler. It monitors a GitHub repository for queued workflow jobs, provisions cloud VMs to run them as ephemeral GitHub Actions runners, and cleans them up when done. The service runs continuously, typically as a systemd unit or as a cloud-deployed service on a small VM.

---

## Source Layout

All source lives under `testflows/github/hetzner/runners/`. Key files:

| File | Role |
|---|---|
| `bin/github-hetzner-runners` | CLI entry point and main runner loop |
| `scale_up.py` | Job detection → VM provisioning → runner registration (~70KB, most complex) |
| `scale_down.py` | Idle runner detection → VM cleanup (~37KB) |
| `config/config.py` | Dataclass-based config: YAML parsing, env var expansion, validation |
| `hclient.py` | Thin wrapper around the Hetzner `hcloud.Client` (21 lines) |
| `cloud.py` | Deploys the runner service itself to a cloud VM |
| `server.py` | SSH utilities, IP extraction, server age; `MockServer` for direct-host connections |
| `actions.py` | Context manager for structured action logging |
| `constants.py` | Label names and naming conventions |
| `args.py` | CLI argument type validators |
| `logger.py` | Structured CSV logging with context-aware field injection |
| `metrics.py` | Prometheus metrics (server creation, job counts, cost) |
| `dashboard/` | Streamlit monitoring dashboard |
| `scripts/deploy/` | Server setup/startup shell scripts |

---

## Runtime Architecture

Three threads run concurrently:

```
api_watch()    — polls GitHub API for queued jobs; publishes to mailbox queue
scale_up()     — consumes mailbox; provisions VMs; registers runners
scale_down()   — independently monitors runners; powers off and deletes idle VMs
```

The mailbox is a thread-safe queue. `scale_up` is the largest and most complex component. All VM operations use SSH — setup and startup scripts run on the remote server after creation.

---

## Label System

Jobs declare their hardware requirements via GitHub runner labels. The runner parses these at job-dispatch time.

| Label format | Meaning |
|---|---|
| `type-{name}` | Request a specific server type (e.g. `type-cx23`) |
| `in-{name}` | Request a specific location (e.g. `in-nbg1` for Hetzner, `in-us-east-1a` for AWS AZ) |
| `image-{arch}-{kind}-{name}` | Request a specific image (e.g. `image-x86-system-ubuntu-22.04`) |
| `setup-{name}` | Run `{name}.sh` from `--scripts` dir during server setup |
| `startup-{name}` | Run `{name}.sh` from `--scripts` dir on each runner start |

Multiple `type-` labels are supported. `get_server_types()` in `scale_up.py` returns all of them as a list; the provisioning loop tries each in order — this is the fallback mechanism.

Server type names containing `-` are skipped by `get_server_types` (they are treated as composite label fragments, not type names). This is intentional.

### Meta-Labels

A single label can expand to a full set of labels via config:

```yaml
meta_label:
  test-arm: [self-hosted, type-cax21, image-arm-system-ubuntu-22.04]
  test-x86: [self-hosted, type-cpx21, image-x86-system-ubuntu-22.04]
```

A job using `runs-on: [test-arm]` is equivalent to `runs-on: [test-arm, self-hosted, type-cax21, image-arm:system:ubuntu-22.04]`. Meta-labels always include themselves in the expansion. The `expand_meta_label()` function in `scale_up.py` handles this.

### Label Prefix

A custom label prefix can be set so multiple runner instances can share a repository without conflicting. With prefix `team-a`, the runner only responds to labels starting with `team-a-` (e.g. `team-a-type-cx23`).

---

## Configuration

Three-tier priority (highest to lowest): CLI arguments → YAML file → environment variables.

Default config path: `~/.github-hetzner-runners/config.yaml` or `$GITHUB_HETZNER_RUNNERS_CONFIG`.

Supports `${ENV_VAR}` expansion in YAML values.

---

## Multi-Provider Design (In Progress)

See `docs/multicloud-plan.md` for the full plan. Key decisions recorded here for agent context:

**Provider selection is implicit, not label-encoded.** Jobs do not specify a provider in their labels. When the runner encounters `type-cx23`, it asks each configured provider whether it offers that type. Provider type namespaces are vendor-specific in practice (Hetzner uses `cx`/`cax`/`ccx` prefixes, AWS uses `t3`/`m5`/`c5`, etc.), so collisions are rare and acceptable.

**`in-` labels map to provider-native location concepts.** For Hetzner this is a DC location (`nbg1`); for AWS this is an AZ (`us-east-1a`), not a region. AZ granularity is intentional — EBS volumes are AZ-scoped, so using AZs now keeps future volume support viable without revisiting the label system.

**Meta-labels are the multi-provider mechanism for jobs.** A meta-label can expand to multiple `type-` labels from different providers, and the existing fallback loop handles trying each:

```yaml
meta_label:
  standard-linux: [type-cx23, type-t3medium]
```

This requires no changes to job workflow files and no new label syntax.

**Abstract interface goes in `cloud_provider.py`.** Hetzner implementation moves to `providers/hetzner.py`. AWS will go in `providers/aws.py`. Provider instances are constructed from config and injected into `scale_up` and `scale_down`.

**Config structure changes.** The top-level `hetzner_token` is replaced by a `providers:` section:

```yaml
providers:
  hetzner:
    token: ${HETZNER_TOKEN}
  aws:
    access_key: ${AWS_ACCESS_KEY}
    secret_key: ${AWS_SECRET_KEY}
    region: us-east-1
```

Backwards compatibility with the existing flat `hetzner_token` config should be preserved during transition.

---

## Conventions

- The codebase uses Python dataclasses for domain objects and config.
- Threading: `scale_up` uses a `ThreadPoolExecutor` for concurrent server creation. Volume operations are protected by `threading.Lock()`.
- All cloud operations are retried with exponential backoff (see `request.py`).
- Metrics are recorded in `metrics.py` using Prometheus counters/histograms. New cloud operations should emit metrics.
- The `Action` context manager (`actions.py`) should wrap any significant operation for structured logging. Use it in provider implementations.
- Do not add error handling for conditions that cannot occur. Validate only at system boundaries.
- Do not add speculative abstractions. Implement what the plan requires, no more.
