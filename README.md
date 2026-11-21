# NEXUS V22 — duel-aware adaptive policy

## V22 changes
- Estimate sustained damage using live weapon stats, ammo/reload, range, energy, and cube scaling. Enemy estimates use public default weapon stats and observed equipment; they are heuristics, not match predictions.
- Favor winnable duels and adjust combat spacing against lightning-equipped opponents. Keep active attackers ahead of farming targets.
- Prioritize early secondary weapons and clusters of cubes; increase safe early travel boosts.
- Prefer armor or plating when under sustained nearby pressure, and energy-efficient lightning upgrades when energy is low.
- 62 unit tests passed; native and fallback protocol checks passed. On the 300 recorded observations, V22 and V21 had identical actions; targeted tests exercise new decisions. No actual V22 match score or Docker execution verified locally.


Derived from the existing V20 package. V9 (4.33) remains the last confirmed competition score. V21 is a hypothesis to test, not a guaranteed improvement.

## Changes
- During multi-opponent fights, favor positions with a clear shot at the selected target and cover from secondary opponents.
- Give a ready, aligned gun priority for lethal shots rather than starting a fresh laser charge.
- Prefer lightning over mortar in close, energy-sufficient multi-opponent fights.
- Discard outdated patrol goals near the end of a zone shrink.
- Three new regression tests; 58 total tests passed. Native and fallback protocol checks each passed 300 observations. V21 and V20 produce identical actions on this short, noninteractive replay; new cases are exercised in targeted tests.

## Submission
Replace the seven files in the update ZIP at the root of your existing GitHub repository. The Dockerfile and runtime dependencies from V20 remain unchanged. Keep previous scored commits public. Submit the commit to the Mech Royale track, then compare its individual scored result. No Docker runtime or interactive match simulator was available locally.

Run `python -m unittest test_bot test_profiles test_v20 test_v21 -q` and `python check/check.py -- python -u bot.py` from the complete package directory.

# NEXUS V20 — adaptive combat prioritization

Submit this variant first, then measure the aggressive and survivor variants separately. V9 (4.33) is the last user-confirmed scored version. V20 is not a match-tested improvement.

## V20 changes
- Prioritize a recent visible attacker over farming targets.
- Exclude crates when selecting a target for return fire during recovery.
- Do not pursue distant loot instead of fighting a vulnerable enemy or recent attacker; nearby loot is still allowed.
- Derive preferred lightning fighting distance from its live range.
- Consider visible incoming projectiles up to 165 m away, still capped at 32 projectiles.
- Four new regression tests, all passed. 55 total test methods passed. Official checker passed with and without native acceleration (600 recorded observations total). Compared with V19, 4 of 300 recorded actions changed. These observations are not a simulator. Actual Docker and battle performance are unverified.

Run: `python -m unittest test_bot test_profiles test_v20` and `python check/check.py -- python -u bot.py`.

# NEXUS V17 — Adaptive

Retreat threshold depends on enemy numbers and relative health, early farming, close-range opportunistic weapon choice.

All three variants share the V14 protocol wrapper, map cache, native acceleration and Dockerfile. Each has its own default policy selected at the top of bot.py. The variants fix empty gun reload requests, improve resource prioritization and widen patrol scans. They only use legal protocol observations and the supplied map.

## Submit
Replace bot.py, test_bot.py, test_profiles.py, README.md and CHECK_RESULTS.txt at the root of the existing NEXUS repository. Do not upload the ZIP itself. Commit directly to the default branch and submit that commit to Mech Royale. The remaining runtime files are unchanged from V14. Keep all submitted commits accessible.

## Tests
`python -m unittest test_bot test_profiles -q` checks 45 test methods, including direct replay and synthetic data for all three profiles. `python check/check.py -- python -u bot.py` checks the selected profile. CHECK_RESULTS.txt contains local native and fallback runs. The recorded observations are not interactive battles. Docker and real match scores are not verified. The confirmed previous score is 4.33; compare the individual attempt scores before choosing the best policy.

## V18 changes
Default policy remains adaptive. If the highest-ranked target has no viable predicted firing solution, examine at most three alternate targets and use the first with a viable weapon. Avoid idle airborne jetting while holding a recovery/capture position. Two targeted regression tests were added (47 total test methods). These are protocol and scenario tests, not actual battle results. The V15/V16/V17 comparison should still be scored separately; this version is an additional candidate, not a demonstrated improvement over 4.33.

## V19 changes
The default remains adaptive. New changes: aim at a reachable portion of the target when its midpoint falls outside pitch limits; orbit NPCs at about 29 m rather than holding still at close range; favor a ready gun over starting a laser charge in a close, multi-opponent fight when mobility matters; allow proactive gun reloads in either slot. Added four regression tests. The bot announces NEXUS-V19-adaptive at startup. The native helper and Dockerfile remain unchanged. No official match score for V19; no local Docker execution. Use a distinct submitted commit SHA for each variant and compare the individual scores. V9's 4.33 is the last confirmed best score supplied by the user.
