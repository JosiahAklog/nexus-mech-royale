# NEXUS V14 — recovery and range corrections

NEXUS uses the official mechfight/1 wrapper, a derived static map cache, standard-library Python, and an optional native C accelerator. Runtime uses only public map information and server observations. No runtime network or writable storage is required.

## Submission
Upload the files at the repository root (not this ZIP). Dockerfile must be at root. Submit the public repository URL at https://www.joinbuilders.org/buildathon/tracks/builders. Keep earlier submitted commits public. If updating an existing V5/V7 repository, files may be replaced by name without deleting older commits. The official arena and check folders are for local testing; runtime needs only the five files copied by Dockerfile.

## V14 changes
- During recovery, engage an exposed nearby NPC drone if it prevents regeneration and no nearby enemy mech takes priority. Resume repair after the threat disappears. Escape at critical HP rather than remaining in range.
- Remove the fixed 220 m targeting ceiling and use current weapon range instead.
- Two regression tests; 42 unit tests total. These are targeted fixes, not verified match-score improvements. V9 remains the proven 4.33 submission.

## V13 changes
- Price resource travel by detours, contested loot and available jet energy.
- Recognize an armed pursuer moving toward us during retreat; continue permitted defensive fire until actual cover is reached.
- Favor cover during weapon downtime and avoid valuing an empty/reloading gun as a simultaneous firing option.
- Suppress non-mech farming fire when urgent zone travel and low health coincide.
- Four regression tests added. The 300 official recorded observations produced identical actions to V12; the new behavior is covered by targeted synthetic tests, not a live match.
- V13 has no measured competition score. V9's user-reported 4.33 is the proven backup. Docker is unavailable locally.

## V12 changes
- Evaluate projectile risk at both walking and intended boosted ground speed; account for laser charge movement slowdown. Do not choose an unsafe sprint merely because the destination is far away.
- Sprint toward safe supply drops and stop inside their capture ring. Increase the priority of a drop already being captured.
- Account for vertical velocity and terrain when predicting airborne targets; derive aim delay from live tick frequency. Require reasonable pitch alignment before beginning a laser charge.
- Allow return fire during recovery when a weak, exposed target is within reach. Keep target lock consistent with the selected target after recovery filtering.
- Prefer a close lightning pickup when the second slot is empty and a nearby fight is likely; avoid swapping a charged laser.
- Five new regression tests. The original map, native C library, official wrapper, checker, and Dockerfile remain unchanged.

V12 is an experimental gameplay candidate, not a demonstrated score increase. V9 scored 4.33 according to the user's leaderboard screenshot. V10 and V11 have no reported match scores. Submit V12 for a real comparison; keep the V9 commit public.

## V11 changes
- Preserve a visible target while a laser is charged; prioritize weak nearby targets and lightning-range engagements.
- Choose an aim based on compatible weapon combinations rather than the highest individual weapon priority alone.
- Recover opportunistically at 70–78% HP when threats and recent damage are absent; avoid premature reloads during an exposed retreat.
- Increase early-game boost use for safe loot and farming, while retaining energy reserves.
- Penalize moving toward secondary opponents during multi-enemy fights; favor lightning against a nearby laser when replacing a mortar.
- Four new regression tests. No changes to the already working native library, Dockerfile, wrapper or map.
These are targeted gameplay hypotheses; no live score is claimed. V9 is the user's confirmed 4.33 backup.

## V10 changes
- Track enemy velocity changes, smooth and clamp extrapolation, and reduce lead when a predicted position intersects the map surface.
- Remember recent attackers; prioritize weakened enemies, weapon matchups and targets near the current aim.
- Prioritize nearby cube clusters, earlier secondary weapon acquisition, gun magazine upgrades and weapon-specific upgrades. Bound the candidate pool for crowded observations.
- Release an aligned laser early when its estimated damage can finish a target; preserve gun/lightning compatibility and gun/laser simultaneous firing where aim permits.
- Seek low reachable roofs during recovery when safe and energy allows; hold the roof plan briefly instead of oscillating.
- Improve pickup travel boosting and reload timing; retain existing zone and recovery safeguards.
- Five new regression tests. Native library, static map, official wrapper and Dockerfile are unchanged from V9. These changes are gameplay hypotheses, not a measured score increase.

## V9 changes
- Return fire during an exposed retreat while under active pressure; stop shooting when safe enough to regenerate. Do not begin a laser charge during recovery.
- Allow lightning and gun fire together when their yaw solutions are compatible; lightning does not require pitch alignment.
- Collect nearby safe cubes while recovering, and reduce the incentive to grow larger after the damage/HP cap when no upgrade is near.
- Preserve supply-drop target altitude and prioritize recent attack direction over a stale tracked enemy when not firing.
- Scan more broadly during safe patrols.
- Add three targeted regression tests. Native code, Dockerfile, wrapper and static map cache are unchanged from V8; rebuilt and compared the native library and map byte-for-byte.

## V8 changes
- Remember recently seen pickups and cubes while outside vision; expire stale entries and never send a take action for an unseen weapon.
- Choose nearby visible weapon pickups in distance order.
- Stop aiming at fully obstructed targets without a mortar.
- Avoid early gun reload while firing or already reloading.
- Skip route waypoints only when a short unobstructed shortcut exists.
- Add future-zone pressure during movement.
- Four new regression tests; retained all previous corrections.

## V7.1 corrections
- Avoid ground boosting near a zone/escape destination; use a damped velocity controller in tiny endgame zones to reduce overshooting.
- Continue a nearly finished supply capture when safe enough, rather than abandoning it because an enemy is nearby outside the ring.
- Check map-cache length before use.
- Two new regression tests. Rebuilt the C accelerator and raster from their sources; both matched the packaged files byte for byte. Official wrapper, schema, map, checker and replay left unchanged.

## Test locally
From repository root:
```
python test_bot.py
python check/check.py -- python -u bot.py
```
Docker Desktop / PowerShell (Linux containers):
```
docker build --platform linux/amd64 -t nexus-mech .
python check/check.py --map-dir /arena -- docker run --rm -i --network none --cpus 1 --memory 512m --read-only --tmpfs /tmp:rw,size=64m --user 65534:65534 -v "${PWD}/arena:/arena:ro" nexus-mech
```
The replay is not a live simulator. Docker was unavailable during this audit. The local restricted-runtime test is an approximation, not Docker validation. The user reported V5 practice score 3.88 and V9 practice score 4.33. V10 actual match score is unknown. The official checker is a non-interactive replay. The final is a separate free-for-all against qualifying competitors.

## Reproduce derived files (optional)
`gcc -O3 -fPIC -shared -Wall -Wextra -Werror -o fastmap.so fastmap.c -lm` (Linux amd64; glibc 2.35+).
`python build_map.py arena/v2 map.bin` (requires numpy, scipy, matplotlib in the generation environment only).
The native helper is optional; if it cannot load, Python fallback algorithms are used. The Dockerfile uses Python 3.13 on Debian Bookworm (glibc 2.36). Map geometry and movement models are approximations; the server is authoritative.
