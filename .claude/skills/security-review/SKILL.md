---
name: security-review
description: Security code review for vulnerabilities. Use when asked to "security review", "find vulnerabilities", "check for security issues", "audit security", "OWASP review", or review code for injection, XSS, authentication, authorization, cryptography issues. Provides systematic review with confidence-based reporting.
allowed-tools: Read, Grep, Glob, Bash, Task
license: LICENSE
---

# Security Review

Identify exploitable security vulnerabilities. Report only **HIGH CONFIDENCE** findings — vulnerable patterns with attacker-controlled input confirmed. Before flagging anything, research the full codebase to trace data flow, check for upstream validation, and confirm the input is not server-controlled. Never report based on pattern matching alone.

## Confidence Levels

| Level | Criteria | Action |
|-------|----------|--------|
| **HIGH** | Vulnerable pattern + attacker-controlled input confirmed | **Report** with severity |
| **MEDIUM** | Vulnerable pattern, input source unclear | **Note** as "Needs verification" |
| **LOW** | Theoretical, best practice, defense-in-depth | **Do not report** |

## Do Not Flag

- Test files, dead code, commented code, documentation strings
- Patterns using constants or server-controlled config (`settings.X`, `os.environ.get('X')`, config files, hardcoded values, signed session data)
- Code paths that require prior authentication to reach

**Framework-mitigated patterns** — check language guide before flagging:

| Pattern | Usually Safe Because | Only Flag When |
|---------|---------------------|----------------|
| Django `{{ var }}` / React `{var}` / Vue `{{ var }}` | Auto-escaped | `\|safe`, `mark_safe(user_input)`, `dangerouslySetInnerHTML={user}`, `v-html="user"` |
| `Model.objects.filter(id=input)` | ORM parameterizes | `.raw()`, `.extra()`, `RawSQL()` with string interpolation |
| `cursor.execute("...%s", (val,))` | Parameterized | String formatting inside the query |

## Review Process

### 1. Detect Context → Load References

| Code Type | Load These References |
|-----------|----------------------|
| API endpoints, routes | `authorization.md`, `authentication.md`, `injection.md` |
| Frontend, templates | `xss.md`, `csrf.md` |
| File handling, uploads | `file-security.md` |
| Crypto, secrets, tokens | `cryptography.md`, `data-protection.md` |
| Data serialization | `deserialization.md` |
| External requests | `ssrf.md` |
| Business workflows | `business-logic.md` |
| GraphQL, REST design | `api-security.md` |
| Config, headers, CORS | `misconfiguration.md` |
| CI/CD, dependencies | `supply-chain.md` |
| Error handling | `error-handling.md` |
| Audit, logging | `logging.md` |

### 2. Load Language Guide

| Indicators | Guide |
|------------|-------|
| `.py`, `django`, `flask`, `fastapi` | `languages/python.md` |
| `.js`, `.ts`, `express`, `react`, `vue`, `next` | `languages/javascript.md` |
| `.go`, `go.mod` | `languages/go.md` |
| `.rs`, `Cargo.toml` | `languages/rust.md` |
| `.java`, `spring`, `@Controller` | `languages/java.md` |

### 3. Load Infrastructure Guide (if applicable)

| File Type | Guide |
|-----------|-------|
| `Dockerfile`, `.dockerignore` | `infrastructure/docker.md` |
| K8s manifests, Helm charts | `infrastructure/kubernetes.md` |
| `.tf`, Terraform | `infrastructure/terraform.md` |
| GitHub Actions, `.gitlab-ci.yml` | `infrastructure/ci-cd.md` |
| AWS/GCP/Azure configs, IAM | `infrastructure/cloud.md` |

### 4. Verify Exploitability

Trace each potential finding: confirm input comes from `request.GET/POST/body/headers/cookies`, URL segments, file uploads, or other-user DB content — not from settings, env vars, or hardcoded values. Check for framework auto-escaping/parameterization and upstream sanitization. Report only HIGH confidence findings.

## Severity Classification

| Severity | Impact | Examples |
|----------|--------|----------|
| **Critical** | Direct exploit, no auth required | RCE, SQL injection, auth bypass, hardcoded secrets |
| **High** | Exploitable with conditions, significant impact | Stored XSS, SSRF to metadata, IDOR to sensitive data |
| **Medium** | Specific conditions required, moderate impact | Reflected XSS, CSRF on state-changing actions, path traversal |
| **Low** | Defense-in-depth, minimal direct impact | Missing headers, verbose errors, weak algorithms in non-critical context |

## Quick Patterns Reference

### Always Flag (Critical)
```
eval(user_input)           # Any language
exec(user_input)           # Any language
pickle.loads(user_data)    # Python
yaml.load(user_data)       # Python (not safe_load)
unserialize($user_data)    # PHP
deserialize(user_data)     # Java ObjectInputStream
shell=True + user_input    # Python subprocess
child_process.exec(user)   # Node.js
```

### Always Flag (High)
```
innerHTML = userInput              # DOM XSS
dangerouslySetInnerHTML={user}     # React XSS
v-html="userInput"                 # Vue XSS
f"SELECT * FROM x WHERE {user}"    # SQL injection
`SELECT * FROM x WHERE ${user}`    # SQL injection
os.system(f"cmd {user_input}")     # Command injection
```

### Always Flag (Secrets)
```
password = "hardcoded"
api_key = "sk-..."
AWS_SECRET_ACCESS_KEY = "..."
private_key = "-----BEGIN"
```

### Check Context First
```
requests.get(request.GET['url'])     # FLAG: user-controlled URL (SSRF)
requests.get(settings.API_URL)       # SAFE: server-controlled
open(request.GET['file'])            # FLAG: user-controlled path (traversal)
open(f"{BASE_DIR}/{filename}")       # CHECK: is 'filename' user input?
redirect(request.GET['next'])        # FLAG: user-controlled redirect
hashlib.md5(password)                # FLAG: password hashing
random.random() for token            # FLAG: use secrets module instead
```

## Output Format

```markdown
## Security Review: [File/Component Name]

### Summary
- **Findings**: X (Y Critical, Z High, ...)
- **Risk Level**: Critical/High/Medium/Low
- **Confidence**: High/Mixed

### Findings

#### [VULN-001] [Vulnerability Type] (Severity)
- **Location**: `file.py:123`
- **Confidence**: High
- **Issue**: [What the vulnerability is]
- **Impact**: [What an attacker could do]
- **Evidence**:
  ```python
  [Vulnerable code snippet]
  ```
- **Fix**: [How to remediate]

### Needs Verification

#### [VERIFY-001] [Potential Issue]
- **Location**: `file.py:456`
- **Question**: [What needs to be verified]
```

If no vulnerabilities found, state: "No high-confidence vulnerabilities identified."
