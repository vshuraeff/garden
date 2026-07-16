# Changelog

## 0.7.2

- Migrated configurations now set `documentation.root_context_required = false`
  so migration does not introduce a new root-context requirement.
- Benchmark v1 records the migration parity result as an honest negative. Its
  detection, evidence, and mutation suites pass; migration remains failed
  because the preregistered invariant conserves legacy classification bugs.
- The ignored TypeScript vendor fixture is tracked in both legacy and configured
  corpus trees, with repository-local ignore negations preventing it from being
  masked by contributor Git configuration.
- Marketplace principle names, checklist implementation status, and README
  evidence claims now match the revised model and measured results.
- CI pins Ruff `0.15.21` for reproducible lint and format checks.

The preceding pre-1.0 revision included semantically incompatible principle
renames and configuration changes that shipped as minor version bumps under the
repository's pre-1.0 SemVer policy. Benchmark v1 is deterministic and non-agent;
agent-task effectiveness remains unmeasured.
