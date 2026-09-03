"""Widget attribution markers (PRD §7.4.1, §7.10; D85).

The website's WhatsApp button deep-links to `wa.me/<number>?text=Hi Veriprops! [ref: web-home]`
(`frontend/src/lib/whatsapp.ts`), so the page a customer came from arrives as **literal text
inside their first message**. §7.10 counts those codes as the channel's demand signal, which
means something has to read the marker back out.

Two rules, and the second is the one worth stating:

* **Extract it.** The code is stored on the inbound row and copied onto the `ENQUIRY` fact.
* **Strip it before anything reads the message as words.** `[ref: web-pricing]` is
  attribution metadata the customer never typed and cannot see themselves having typed —
  their phone rendered it into the box. Leaving it in means the intent classifier scores a
  fragment of markup, the guardrails match against it, and the admin console shows an agent
  a message their customer did not write. The raw Meta envelope is retained untouched on
  `whatsapp_inbound_messages.payload`, so nothing is lost by cleaning the readable copy.

A message that is *only* the marker normalizes to no text at all rather than to an empty
string, so the bot treats it as the greeting it is and answers with the §7.6.1 welcome.
"""
from __future__ import annotations

import re
from typing import Optional, Tuple

# `[ref: web-home]`, as `waMeUrl`/`waContinueUrl` emit it. Case-insensitive and tolerant of
# spacing because the customer's keyboard, WhatsApp's own link preview, and a forwarded
# message can each re-wrap it. The code charset matches the frontend's slugifier — it
# derives `web-<segment>` for any unlisted page, so an unfamiliar code is a new page rather
# than bad data, and there is deliberately no allow-list here to reject it.
_MARKER = re.compile(r"\[\s*ref\s*:\s*([A-Za-z0-9][A-Za-z0-9_-]{0,39})\s*\]", re.IGNORECASE)


def extract_page_code(text: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    """Split a message into its attribution code and the words the customer meant.

    Returns ``(page_code, cleaned_text)``. Both are ``None`` when absent — an empty string
    would be a message with no words, which is a different thing from a message that was
    nothing but a marker.

    Only the **first** marker is honoured. A second one is stripped along with it but does
    not overwrite the code: a forwarded conversation can carry someone else's marker, and
    the page this customer arrived from is the one their own phone put there first.
    """
    if not text:
        return None, text

    match = _MARKER.search(text)
    if not match:
        return None, text

    page_code = match.group(1).lower()
    cleaned = _MARKER.sub(" ", text)
    # Collapse the gap the removal leaves, so "Hi Veriprops!  " does not reach the
    # classifier with the shape of a message that trailed off.
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return page_code, (cleaned or None)
