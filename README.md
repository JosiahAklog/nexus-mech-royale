# NEXUS V9 — tested combat and recovery update

NEXUS uses the official mechfight/1 wrapper, a derived static map cache, standard-library Python, and an optional native C accelerator. Runtime uses only public map information and server observations. No runtime network or writable storage is required.

## Submission
Upload the files at the repository root (not this ZIP). Dockerfile must be at root. Submit the public repository URL at https://www.joinbuilders.org/buildathon/tracks/builders. Keep earlier submitted commits public. If updating an existing V5/V7 repository, files may be replaced by name without deleting older commits. The official arena and check folders are for local testing; runtime needs only the five files copied by Dockerfile.

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
The replay is not a live simulator. Docker was unavailable during this audit. The local restricted-runtime test is an approximation, not Docker validation. Actual V9, V8 and V7.1 scores are unknown. The V9 changes are hypotheses, not verified improvements in live match placement. The official checker is a non-interactive replay. The prior V5 practice score reported by the team was 3.88.

## Reproduce derived files (optional)
`gcc -O3 -fPIC -shared -Wall -Wextra -Werror -o fastmap.so fastmap.c -lm` (Linux amd64; glibc 2.35+).
`python build_map.py arena/v2 map.bin` (requires numpy, scipy, matplotlib in the generation environment only).
The native helper is optional; if it cannot load, Python fallback algorithms are used. The Dockerfile uses Python 3.13 on Debian Bookworm (glibc 2.36). Map geometry and movement models are approximations; the server is authoritative.
