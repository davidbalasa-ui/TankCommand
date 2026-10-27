# Requirements

| ID | Description |
| --- | --- |
| SIM-01 | Same seed and command list produce the same world hash after 10,000 steps. |
| SIM-02 | Different seeds produce different world hashes after 100 steps. |
| SIM-03 | World stepping does not mutate its input and accepts frozen input. |
| SIM-04 | Counter commands apply only on their tick and past ticks are ignored. |
| SIM-05 | Command validation rejects malformed commands. |
| SIM-06 | Fixed-step loop accumulates, caps and ignores invalid elapsed time. |
| SIM-07 | Seeded RNG is reproducible, resumable and respects exclusive upper bounds. |
| ASSET-01 | The real asset manifest validates. |
| ASSET-02 | Manifest rejection cases name the offending asset id. |
| ASSET-03 | Every manifest file exists and matches the recorded byte size. |
| ASSET-04 | Concurrent loads for one asset share one fetch. |
| ASSET-05 | Failed loads are not cached and can retry. |
| ASSET-06 | Refcounting keeps cached assets until final release and disposes once. |
| ASSET-07 | Preload reports progress, caches successes and reports every failure. |
| ASSET-08 | Byte size mismatches reject with AssetLoadError. |
| ASSET-09 | Credits check passes on committed files and fails when the manifest changes. |
| ASSET-10 | The browser loads the real tank model through registry, loader and GLTF decoder. |
| DATA-01 | The placeholder unit table loads against the real asset manifest. |
| DATA-02 | Unit data validation rejects the specified malformed rows. |
| DATA-03 | Placeholder reporting lists placeholder rows and drops tuned rows. |
| SAVE-01 | Save round trip preserves deterministic simulation state. |
| SAVE-02 | Save decoding returns specific failure reasons and never throws. |
| SAVE-03 | Autosave rotation keeps three slots and identifies the newest. |
| SAVE-04 | Exceeding the byte cap rejects without destroying previous saves. |
| SAVE-05 | Web storage quota failures map to StorageFullError. |
| LIFE-01 | Lifecycle events deduplicate pause and map back to pause plus back. |
| WD-01 | Watchdog freeze and recover fire once per episode and reset on beat. |
| WD-02 | Suspended watchdog suppresses freezes and resets clocks on unsuspend. |
| WD-03 | Global error capture records errors and rejected promises. |
| WD-04 | A frozen sim shows the recovery screen with all recovery controls. |
| UI-01 | Every screen mounts and unmounts without leaving DOM nodes behind. |
| UI-02 | Overlays stack and back pops settings then pause to inGame. |
| UI-03 | Rapid repeated navigation to one screen mounts only one DOM root. |
| UI-04 | Every registered control id is listed in the control inventory file. |
| UI-05 | E2E controls meet touch target size and do not overlap across the main flow. |
| LINT-01 | Lint runs with zero warnings. |
| LINT-02 | Sim lint restrictions fire on sim files and not render files. |
| LINT-03 | The sim TypeScript config excludes the DOM library. |
| REQ-01 | Requirement coverage passes and fails when an untested id is appended. |
| CI-01 | The GitHub workflow runs the full CI and E2E commands. |
| CAP-01 | Capacitor config has the required app id, web dir and no server URL. |
| BUILD-01 | The built app uses relative asset URLs and copies public assets. |
| HOOK-01 | Production builds contain no test hook marker or window hook. |
| HOOK-02 | Test hook commands are validated and invalid commands do nothing. |
| REND-01 | The canvas is non-blank and frame count increases. |
| REND-02 | Hiding the page stops frames and resuming does not jump sim time. |
