# Commands

Each file describes one Claude Code slash command for the QA domain skill.

| File | Command | When to use |
|---|---|---|
| `init-qa-platform.md` | `/qa init-qa-platform` | First time setting up the platform in a repo |
| `add-domain.md` | `/qa add-domain` | Adding a new domain for a feature area |
| `upgrade-domain.md` | `/qa upgrade-domain` | Regenerating a domain after app changes |
| `remove-domain.md` | `/qa remove-domain` | Removing a domain entirely |
| `scan-domains.md` | `/qa scan-domains` | Listing all domains and their current status |
| `sync-domains.md` | `/qa sync-domains` | Reconciling manifest with filesystem |
| `validate-domain.md` | `/qa validate-domain` | Validating a single domain in depth |
| `validate-all-domains.md` | `/qa validate-all-domains` | Validating every registered domain |
| `drift-report.md` | `/qa drift-report` | Reporting schema version drift across domains |

## Usage

Invoke commands in Claude Code with the `/qa` prefix:

```
/qa add-domain
/qa upgrade-domain --domain checkout
/qa drift-report
```

Always read `SKILL.md` before executing any command.
