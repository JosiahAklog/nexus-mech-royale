# NEXUS V35 — Persistent Threat Awareness

Built from the exact V34 complete ZIP. Confirmed competitive best reported by the user: V28.1, 4.96. The V34 prediction of 5.72 is hypothetical, not measured. Target: 6.00+.

## Changes from V34
- Track recent attackers independently for twelve seconds, so zone damage or another attacker does not immediately erase a known ranged threat.
- Continue avoiding a recently damaging, exposed long-range shooter during repairs, and react to visible aimed charging lasers even when no recent attack is recorded. Allow repairs once terrain blocks the threat.
- Prefer moving away from an exposed attacker rather than a nearby opponent behind cover.
- Face the ranged threat when retreating without firing or releasing a charged laser, reducing potential rear-armor exposure.
- Account for part of the actual healing duration when choosing future-safe escape cover.
- Clear stale altitude targets when final-zone centering overrides the earlier objective.

All earlier resource, energy, targeting, navigation and native acceleration routines are retained except for these specific changes. No interactive match simulator was available. The fixed replay only validates protocol and illustrates decisions; it cannot determine placement improvements.

## Upload
If V34 is already uploaded, extract the four-file V35 update and upload to the repository root. Otherwise use the complete ZIP, preserving arena/v2 and check. Keep the highest confirmed entry selected until a better official result is available.

See CHECK_RESULTS.txt for local verification.
