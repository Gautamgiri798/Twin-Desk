# Feature Development Workflow

## Required feature brief

Every feature PR should include:
- Problem and user story.
- Requirements/issue IDs.
- Scope and non-goals.
- Design/API changes.
- Security and privacy impact.
- Tests and acceptance criteria.
- Known limitations.

## Workflow

1. Read the relevant PRD/TRD section.
2. Write a small implementation plan.
3. Add/update types and protocol schemas before implementation.
4. Implement the smallest vertical slice.
5. Add unit tests and integration tests where possible.
6. Run formatting, linting and tests.
7. Review logs and error handling.
8. Update docs and changelog.
9. Test the happy path and at least one failure path.
10. Submit a reviewable commit.

## Branch and commit conventions

- Branches: `feat/<short-name>`, `fix/<short-name>`, `docs/<short-name>`, `security/<short-name>`.
- Commits: imperative and focused, e.g. `Add pairing state model`.
- Do not mix unrelated refactors with a feature.

## Feature flags

Use explicit flags for experimental native features. The UI must disclose experimental status and must not silently fall back from "extended desktop" to mirroring.

## Acceptance checklist

- [ ] Requirement mapped to implementation.
- [ ] Unit tests added.
- [ ] Failure behavior tested.
- [ ] Security review completed if input/network/driver involved.
- [ ] Documentation updated.
- [ ] No secrets or sensitive logs.
- [ ] All tests pass.
- [ ] Limitations described accurately.
