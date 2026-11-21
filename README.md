# NEXUS V28.1 — audited tactical candidate

Based on V27 locally; V26 (4.83) is the latest user-confirmed competitive result. V27 has no reported score. V28 is an experimental candidate targeting improved placement, not a certified 6.95 score.

## Changes
- Two-second combat budget accounts for partially compatible second weapons, gun reloads, laser charge, lightning energy, range-dependent estimated accuracy, armor and rear exposure.
- Recent damage burst can trigger earlier retreat against dangerous opponents; movement favors lateral evasion while under fire.
- Future-zone feasibility filters risky distant weapons, cubes and supply drops.
- Online patrol coverage favors recently unvisited, walkable, visible ground when no immediate goal is available and cube count is below 10.
- Retreat energy recharge hysteresis prevents repeated short boosts when reserves are low, except against close threats or in a zone emergency.
- Recent unseen damage bearing guides escape; slightly longer quiet interval before standing still for repair.

All decisions use current protocol observations, remembered observations, and the supplied public map. V27's core targeting, projectile avoidance, runtime dependencies and Dockerfile are retained.

## V28.1 audit corrections
- Use the configured rear-armor multiplier and front arc on both sides of the combat estimate.
- Calculate supply-drop completion as max(travel time, time to landing) plus capture time, instead of combining landing and capture as a single maximum.
- Four additional regression tests; no broad tuning of V28 strategies.

## Validation
Run `python -m unittest discover -q` and `python check/check.py -- python -u bot.py` from the complete package. See CHECK_RESULTS.txt. The checker plays recorded observations and does not simulate battle outcomes. Docker runtime and actual standings were not tested here. Keep the highest-scoring prior commit available and compare the official score for this candidate separately.

## Upload
If V28 is already present in GitHub, upload the four files in the V28.1 Audit Update ZIP to the root and commit them. Otherwise use the complete ZIP, preserving `arena/v2/` and `check/` folders. Submit the new commit to the competition, without replacing the best final entry until a better official score is returned.
