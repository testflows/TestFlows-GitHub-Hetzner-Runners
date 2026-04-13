# Multi-Cloud Support — Plan

Live planning document for the multi-cloud refactor. Update as decisions are made and phases complete.

---

## Goal

Extend the runner service to support multiple cloud providers beyond Hetzner. AWS is the first target. The design should leave the door open for GCP and others without requiring upfront implementation.

---

## Design Decisions

### Provider selection is implicit

Jobs do not specify a provider in their labels. When `scale_up` encounters `type-cx23`, it queries each configured provider to find one that offers that type. Vendor type namespaces are distinct in practice (Hetzner: `cx`/`cax`/`ccx`; AWS: `t3`/`m5`/`c5`/`t4g` etc.), so collisions are unlikely and acceptable.

If explicit provider targeting is ever needed, it can be added later without breaking existing usage.

### Meta-labels are the multi-provider job interface

Job authors remain provider-agnostic. The config owner maps logical names to provider-specific hardware:

```yaml
meta_label:
  standard-linux: [type-cx23, type-t3medium]
```

The existing fallback loop in `scale_up` (which already iterates through all matched server types) handles trying each option. No changes to job workflow files, no new label syntax.

### New files for the abstraction layer

- `cloud_provider.py` — abstract `CloudProvider` base class
- `providers/hetzner.py` — Hetzner implementation (refactored from existing code)
- `providers/aws.py` — AWS implementation

### Config structure

Replace top-level `hetzner_token` with a `providers:` section. Preserve backwards compatibility with the old flat format during transition.

```yaml
providers:
  hetzner:
    token: ${HETZNER_TOKEN}
  aws:
    access_key: ${AWS_ACCESS_KEY}
    secret_key: ${AWS_SECRET_KEY}
    region: us-east-1
```

### Tag/label abstraction

Providers use tags/labels internally to identify and track runner servers. This is an implementation detail of each provider — the shared scaling logic does not construct tag names or dicts directly.

The `CloudProvider` interface exposes:
- A generic metadata API: `get_server_tag`, `set_server_tag`, `list_servers_with_tag` — provider normalises keys/values to its own format and character restrictions
- `list_runner_servers()` — provider-managed; each provider uses its own tag names to identify servers it manages

Tag keys used by shared code must be lowercase alphanumeric and hyphens only (the most restrictive common subset across known providers). Hetzner's existing tag names (e.g. `github-hetzner-runner`) are preserved as-is inside `HetznerCloudProvider` — no migration, no breakage for existing deployments.

### Image labels for AWS

The `image-{arch}-{kind}-{name}` label format is Hetzner-specific. For AWS, jobs specify an AMI using the label format `image-ami-{id}` (e.g. `image-ami-0abc1234`). The provider is responsible for interpreting the image portion of the label in a way that makes sense for it.

### Recycling

Recycling (powered-off server reuse via image reinstall) is Hetzner-only and will not be supported on AWS. On Hetzner it is necessary due to resource availability constraints; on AWS instance availability is not a comparable concern. The `CloudProvider` interface will expose a `supports_recycling` property; recycling logic in `scale_up`/`scale_down` is gated on this.

### Volumes

Volumes are deferred for AWS. The volume label system will not be implemented for `AWSCloudProvider` in the initial release. The `CloudProvider` interface should not preclude a future volume implementation — design interface methods for volumes but leave them unimplemented (raise `NotImplementedError`) in `AWSCloudProvider` for now.

### `cloud deploy` command

The `cloud deploy` command (which provisions the runner service itself onto a cloud VM) remains Hetzner-only. This is documented but not a blocker.

### Testing scope

- Test the `CloudProvider` interface boundary and the two implementations against a shared test suite
- Test label parsing functions (`get_server_types`, `get_server_locations`) — pure functions, easy to test, will be modified
- One smoke test: mock provider injected into `scale_up`, verify correct provider calls on job dispatch
- Do not test individual provider SDK calls or the full scaling loop in detail

---

## Implementation Phases

### Phase 1 — Abstract interface + Hetzner refactor
*No new functionality. Existing behaviour must be identical after this phase.*

- [ ] Define `CloudProvider` abstract base class in `cloud_provider.py`
  - Server lifecycle: create/delete/get/list/list_runner_servers
  - Metadata: get_server_tag/set_server_tag/list_servers_with_tag
  - Resource discovery: list available types, locations, images
  - SSH keys: create/delete/get
  - Volumes: define interface methods (stubs only for now)
  - Properties: `name`, `supports_recycling`
- [ ] Implement `HetznerCloudProvider` in `providers/hetzner/provider.py` by extracting Hetzner-specific code from `scale_up.py`, `scale_down.py`, and `hclient.py`
- [ ] Inject provider into `scale_up` and `scale_down` (replace direct `client` usage)
- [ ] Write tests for the `CloudProvider` interface against `HetznerCloudProvider` (with a mock Hetzner backend)
- [ ] Verify all existing behaviour unchanged

### Phase 2 — Config changes

- [ ] Add `providers:` section to config schema
- [ ] Support backwards-compatible `hetzner_token` flat format (warn on use, still works)
- [ ] Provider factory: construct and return the right `CloudProvider` instance(s) from config

### Phase 3 — Provider type resolution

- [ ] When `scale_up` iterates server types, resolve which provider to use for each type name
- [ ] Query each active provider: "do you have a type named X?" — use the first match
- [ ] Handle the case where no provider recognises a type name (clear error message)
- [ ] Update `get_server_types`, `get_server_locations`, `get_server_image` to operate on abstract provider types
- [ ] Map `in-` labels to provider locations: Hetzner interprets as DC location (e.g. `nbg1`), AWS interprets as AZ (e.g. `us-east-1a`). AZ-level placement ensures future EBS volume support works without revisiting the label system.

### Phase 4 — AWS implementation

- [ ] Implement `AWSCloudProvider` in `providers/aws/provider.py`
  - EC2 instance lifecycle (create/delete/get/list)
  - Tag-based server identification
  - AMI image resolution (`image-ami-{id}` label format)
  - EC2 key pair management
  - No recycling (`supports_recycling = False`)
  - Volumes: `NotImplementedError` stubs
- [ ] Run the shared provider test suite against `AWSCloudProvider`
- [ ] Validate end-to-end with a real AWS account

### Phase 5 — Config validation library (deferred)

Consider migrating `config/parse.py` to Pydantic v2. Currently ~453 lines of manual validation; a Pydantic `BaseModel` Config would reduce this by ~60%. The cost is that Config must change from a dataclass to a `BaseModel`, touching every construction site.

**Do this after Phase 2**, once the dual-representation issue (flat `default_image`/`default_server_type` fields alongside `providers.X.defaults`) is resolved and Config has a stable final shape. Migrating before that means migrating twice.

- [ ] Migrate `Config` to Pydantic `BaseModel`
- [ ] Replace `parse.py` validation boilerplate with field annotations and `@field_validator`s
- [ ] Preserve `config.field_name: error message` error format via custom error handling
- [ ] Provider-specific config parsing moves to `providers/X/config.py` as Pydantic sub-models

### Phase 6 — Polish

- [ ] Update meta-label examples in config/docs to show multi-provider patterns
- [ ] Update `servers` CLI command to list across providers
- [ ] Update dashboard to show provider per runner
- [ ] Update `README.rst` and `docs/requirements.md`
- [ ] Document `cloud deploy` as Hetzner-only
- [ ] Binary/package naming decision

---

## Open Questions

*None currently open.*
