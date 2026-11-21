# NEXUS V36 — Resource-first rollback candidate

V36 starts from the archived V28.1 complete package, not the lower-scoring V35. V28.1 was previously reported at 4.96; V35 was reported at 4.69. The latest user message says 4.86 is the best entry; the official receipt should determine the true final best. This candidate has no competitive score yet.

## Strategy
- Healthy under-equipped mechs prioritize accessible second weapons, with a larger reward for ground-level lasers and no extra priority for contested or elevated pickups.
- Prefer productive nearby crate and drone farming over full-health, distant, unengaged opponents; active attackers keep their original priority.
- Use surplus energy to travel faster during early patrols and resource collection, preserving an escape reserve and the baseline projectile-risk gate.
- Keep the baseline combat, recovery thresholds and defensive movement policy rather than accumulating V29–V35 heuristics.
- Correct stale routes on objective changes and avoid clamping viable loot and drop positions to an unnecessarily large zone margin.
- Keep charged laser aim when available (except for higher-priority lethal gun shots) and charge enough to destroy a crate in one shot when possible.
- Do not suppress a meaningful projectile dodge by braking near loot; preserve final-zone braking.

## Verification and limits
Run `python -m unittest discover -q` in this clean extracted package, and `python check/check.py -- python -u bot.py`. See CHECK_RESULTS.txt for measured results. The checker is a fixed recorded stream, not an interactive simulator. No Docker run or competitive score was available in this environment. The candidate changes 38 of 300 recorded actions, all boost flags; the other changes were verified only in targeted scenarios. No score is guaranteed.

## Upload over V35
Upload the six files from the V36 rollback update ZIP. It includes both `fastmap.c` and `fastmap.so` from V28.1 because V35 changed them. Leave `arena/` and `check/` unchanged. Docker copies only runtime assets. Old test_v29.py through test_v35.py are for later strategies that are deliberately removed; delete them if you want to run the clean V36 test suite in the GitHub checkout, or use the complete ZIP locally. Keep the highest-scoring official submission selected until this candidate is scored higher.
