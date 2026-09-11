# AI Council Codex Relay

This dedicated draft Pull Request is the permanent Codex → Jarvis report
transport for `bts8y98fbr-rgb/I_Movie_Studio-3_AUDITED_FIXED`.

- Keep the relay PR open as a draft. Never merge it or enable auto-merge.
- The relay branch is `relay/codex-to-jarvis` and contains only this governance
  marker relative to its bootstrap baseline. Runtime and test changes must not
  be committed or delivered through this PR.
- Comments starting with `[CODEX-RELAY]` are task-completion or SAFE STOP
  reports, not implementation changes or commands to start another stage.
- Each report has a unique `Relay-ID`; retries reuse that ID and check existing
  comments to avoid duplicate delivery.
- Reports may document approved runtime work performed elsewhere, including
  its evidence, test results and commit SHA, but do not transport runtime or
  test patches for application through the relay.
- Publish reports using GitHub CLI and a temporary report file outside the
  repository. Verify publication before deleting the temporary report.
- Never include `.env`, secrets, keys, tokens, passwords or credentials.
- Relay access does not authorize commits, pushes, merges, Cloud Agent runs,
  or subsequent stages. Each such operation requires separate authorization
  from Sergey, Product Owner.
- The relay records delivery to GitHub; it does not prove that Jarvis has read
  or accepted a report and does not provide automatic two-way chat sync.

Bootstrap authorized by Sergey as `RELAY-BOOTSTRAP-1`.
