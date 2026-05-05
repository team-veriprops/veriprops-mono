# Routing Determinism Report

## Key Design: `"exclusive"` Rule Flag

A routing rule with `"exclusive": True` prevents `_handle_fallback()` from using the "last resort" path (which would try all remaining registered providers). Without this flag, even an empty `fallback_order` was insufficient — the last-resort block would still try Mailjet or Sendgrid after an SMTP failure.

**How it works in `_handle_fallback()`:**
```python
# After exhausting fallback_order from the matched rule:
if channel in self.routing_rules:
    for rule in self.routing_rules[channel]["rules"]:
        if failed_provider.name in rule.get("providers", []) and rule.get("exclusive"):
            raise IntegrationFatalException(
                f"Provider '{failed_provider.name}' failed and its routing rule is "
                f"exclusive — no last-resort fallback allowed for channel '{channel}'."
            )

# Last resort: any remaining provider not yet attempted.
# (only reached if no exclusive rule matched)
```

---

## Email Routing

### Test / Development / Local environments

| Property | Value |
|---|---|
| Rule condition | `ENVIRONMENT not in {PRODUCTION, STAGING}` |
| Primary provider | `SmtpEmailProvider` (Mailpit on `localhost:1025`) |
| `fallback_order` | `[]` (empty — no fallback) |
| `exclusive` | `True` — no last-resort fallback |
| Default (if rule doesn't match) | N/A — rule always matches in non-prod |

**Behavior:** All email captured by Mailpit. If SMTP fails (e.g., Mailpit not running), `IntegrationFatalException` is raised immediately. Mailjet and Sendgrid are **never contacted** in these environments.

### Production / Staging environments

| Property | Value |
|---|---|
| Rule condition | Does not match (condition is false) |
| Default providers | `[MAILJET, SENDGRID_EMAIL]` |
| Fallback | Sendgrid if Mailjet fails; last-resort tries all remaining |

**Defense-in-depth:** `SmtpEmailProvider.send_message()` raises `ValueError` if called in production or staging — even if misconfigured routing somehow selected it.

---

## SMS Routing

### Test / Development / Local environments

| Property | Value |
|---|---|
| Rule condition | `ENVIRONMENT in {TEST, DEVELOPMENT, LOCAL}` |
| Primary provider | `MockSmsProvider` (logs, no real SMS) |
| `fallback_order` | `[]` (empty — no fallback) |
| `exclusive` | `True` — no last-resort fallback |
| Rule priority | First in list — evaluated before Nigerian-number and high-priority rules |

**Behavior:** All SMS is intercepted by `MockSmsProvider`. The message is logged:
```
[MockSmsProvider] SMS suppressed in test. To: +234xxxxxxxxxx | Text: Your OTP is...
```
Returns `SENT` status. Termii and Twilio are **never contacted** in these environments.

**Defense-in-depth:** `MockSmsProvider.send_message()` raises `ValueError` if called in production or staging.

### Production / Staging environments

The mock rule condition is false (`ENVIRONMENT` not in the test set), so evaluation falls through to:

| Rule | Condition | Providers | Fallback |
|---|---|---|---|
| Nigerian numbers | `recipient.startswith("+234")` | `TERMII_SMS` | `TWILIO_SMS` |
| High priority | `priority == "high"` | `TWILIO_SMS` | `TERMII_SMS` |
| Default | none matched | `TWILIO_SMS, TERMII_SMS` | last resort |

---

## Summary Table

| Environment | Email Provider | SMS Provider | Fallback Allowed |
|---|---|---|---|
| `local` | Mailpit (SMTP) | MockSmsProvider | No (exclusive) |
| `dev` | Mailpit (SMTP) | MockSmsProvider | No (exclusive) |
| `test` | Mailpit (SMTP) | MockSmsProvider | No (exclusive) |
| `staging` | Mailjet → Sendgrid | Termii → Twilio | Yes |
| `prod` | Mailjet → Sendgrid | Termii → Twilio | Yes |
