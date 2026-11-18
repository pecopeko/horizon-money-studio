# Track 3 Submitted OSS Pull Requests & Anti-Honeypot Audit

## Live Submitted Pull Requests

### 1. `tscircuit/cli#5654` -> [PR #5858](https://github.com/tscircuit/cli/pull/5858) (Open)
- **Repository**: `tscircuit/cli` (eligible for `tscircuit/contribution-tracker` weekly GitHub Sponsors cash payouts)
- **Target Issue**: https://github.com/tscircuit/cli/issues/5654 (`tsci export -f glb can't load a relative cadModel stepUrl (404); build --glbs can`)
- **Pre-Submission Competition Audit**: `0` issue comments, `0` competing open PRs (`has_competing_open_pr("tscircuit/cli", 5654) == False`)
- **Fork & Branch**: `pecopeko:fix/export-glb-relative-step-url-5654` (`c8345f0`)
- **Root Cause**: `exportSnippet()` in `lib/shared/export-snippet.ts` passed raw `circuitJson` to `convertCircuitJsonToGltf()` for `"gltf"` and `"glb"`, leaving relative paths like `./libraries/cap.step` unresolved so `circuit-json-to-gltf` fetched them from `projectBaseUrl` (`404 Not Found`), whereas `tsci build --glbs` called `convertModelUrlsToFileUrls()`.
- **Fix Summary**:
  - Updated `convertModelUrlsToFileUrls(circuitJson, baseDir?)` in `cli/build/convert-model-urls-to-file-urls.ts` to resolve relative `.` URLs against `projectDir` when present on disk, falling back to `process.cwd()`.
  - Applied `convertModelUrlsToFileUrls(circuitJson, projectDir)` in `lib/shared/export-snippet.ts` for `"gltf"` and `"glb"` exports.
  - Added end-to-end regression test in `tests/cli/export/export-glb.test.ts` validating both `-f glb` and `-f gltf` outside `process.cwd()`.
- **Local Verification (100% Pass Before Opening PR)**:
  - `bun test tests/cli/export/export-glb.test.ts tests/cli/export/export-output-path.test.ts tests/cli/build/build-preview-gltf-relative-path.test.ts --timeout 45000`: **6 pass, 0 fail** (26 `expect()` calls)
  - `bun run format:check` (`biome format .`): **Checked 646 files, 0 issues**
  - `NODE_OPTIONS="--max-old-space-size=3584" ./node_modules/.bin/tsc --noEmit`: **exit 0**

### 2. `tscircuit/core#5677` -> [PR #5680](https://github.com/tscircuit/core/pull/5680) (Open)
- **Repository**: `tscircuit/core` (eligible for `tscircuit/contribution-tracker` weekly GitHub Sponsors cash payouts)
- **Target Issue**: https://github.com/tscircuit/core/issues/5677 (`<board autorouter={{ traceClearance: "0.5mm" }} />` doesn't seem to be working)
- **Pre-Submission Competition Audit**: `0` competing open PRs (`has_competing_open_pr("tscircuit/core", 5677) == False`)
- **Fork & Branch**: `pecopeko:fix/board-autorouter-trace-clearance-5677` (`2c03e61`)
- **Root Cause**: `getPresetAutoroutingConfig()` dropped `traceClearance` when resolving object configs with presets, and `Group` / `getSimpleRouteJsonFromCircuitJson()` did not propagate `autorouterConfig.traceClearance` (or `pcb_group.autorouter_configuration.trace_clearance`) into `SimpleRouteJson.minTraceToPadEdgeClearance`.
- **Fix Summary**:
  - Preserved `traceClearance` across preset expansion in `lib/utils/autorouting/getPresetAutoroutingConfig.ts`.
  - Propagated `traceClearance` into `SimpleRouteJson.minTraceToPadEdgeClearance` (preserving stricter explicit `minTraceToPadEdgeClearance` via `Math.max` and supporting subcircuit groups) in `lib/components/primitive-components/Group/Group.ts` and `lib/utils/autorouting/getSimpleRouteJsonFromCircuitJson.ts`.
  - Added regression coverage in `tests/features/autorouter-trace-clearance.test.tsx`.
- **Local Verification (100% Pass Before Opening PR)**:
  - `bun test tests/features/autorouter-trace-clearance.test.tsx tests/features/autorouter-allow-via-in-pad.test.tsx tests/features/autorouter-min-via-dimensions.test.tsx tests/features/autoroutingphase-region-reroute.test.tsx`: **6 pass, 0 fail** (38 `expect()` calls)
  - `./node_modules/.bin/biome format` (4 touched files): **Checked 4 files, 0 issues**
  - `NODE_OPTIONS="--max-old-space-size=3584" ./node_modules/.bin/tsc --noEmit`: **exit 0**

## Honeypot & Non-Cash Orgs Excluded During Discovery
- Blocklisted AI-honeypot / duplicate synthetic orgs: `SecureBananaLabs`, `UnsafeLabs`, `ClankerNation`, `IES-BoilerRoom`, `zhangjiayang6835-cyber`
- Flagged non-cash credit-only org: `hanzoai` (rewards in platform credits rather than cash)
- Skipped contested `tscircuit` issues that already had open competing PRs (`tscircuit/jlcsearch#653`, `tscircuit/circuit-json-to-spice#73`, `tscircuit/core#6066`)
