# Track 3 Submitted OSS Pull Requests & Anti-Honeypot Audit

## Live Submitted Pull Requests

### 1. `tscircuit/cli#5654` -> [PR #5858](https://github.com/tscircuit/cli/pull/5858) (Open — 14/14 CI checks green)
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

### 2. `tscircuit/core#5677` -> [PR #5680](https://github.com/tscircuit/core/pull/5680) (Open — 18/18 CI checks green)
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

### 3. `tscircuit/core#3982` -> [PR #5684](https://github.com/tscircuit/core/pull/5684) (Open)
- **Repository**: `tscircuit/core` (eligible for `tscircuit/contribution-tracker` weekly GitHub Sponsors cash payouts)
- **Target Issue**: https://github.com/tscircuit/core/issues/3982 (`SCHEMATIC_COMPONENT_OUTLINE_COLOR "rgba(132, 0, 0)" is not portable SVG color; strict SVG renderers reject schematic output`)
- **Pre-Submission Competition Audit**: `0` competing open PRs (`has_competing_open_pr("tscircuit/core", 3982) == False`)
- **Fork & Branch**: `pecopeko:fix/schematic-outline-color-rgb-3982` (`58ed612`)
- **Root Cause**: `SCHEMATIC_COMPONENT_OUTLINE_COLOR` in `lib/utils/constants.ts` used CSS Color Level 4 3-argument `"rgba(132, 0, 0)"`, which strict SVG 1.1 / CSS2 renderers (such as CairoSVG) reject. Switching to `"rgb(132, 0, 0)"` produces the identical color and matches `INLINE_NET_LABEL_COLOR` and `circuit-to-svg` default styling.
- **Fix Summary**:
  - Updated `SCHEMATIC_COMPONENT_OUTLINE_COLOR` in `lib/utils/constants.ts` to `"rgb(132, 0, 0)"`.
  - Added regression test in `tests/utils/schematic/schematic-component-outline-color.test.tsx` validating `schematic_rect`, `schematic_line`, `schematic_circle`, `schematic_arc`, port stems, and `convertCircuitJsonToSchematicSvg` output.
- **Local Verification (100% Pass Before Opening PR)**:
  - `./node_modules/.bin/biome check lib/utils/constants.ts tests/utils/schematic/schematic-component-outline-color.test.tsx`: **Checked 2 files, 0 issues**
  - `bun test --timeout 30000 tests/utils/schematic/schematic-component-outline-color.test.tsx tests/components/primitive-components/schematic-rect.test.tsx tests/components/primitive-components/schematic-line.test.tsx tests/components/primitive-components/schematic-circle.test.tsx tests/components/primitive-components/schematic-arc.test.tsx tests/components/primitive-components/port-sch-stem-length.test.tsx`: **6 pass, 0 fail** (33 `expect()` calls)
  - `NODE_OPTIONS="--max-old-space-size=3584" ./node_modules/.bin/tsc --noEmit`: **exit 0**

### 4. `tscircuit/core#3521` -> [PR #5689](https://github.com/tscircuit/core/pull/5689) (Open)
- **Repository**: `tscircuit/core` (eligible for `tscircuit/contribution-tracker` weekly GitHub Sponsors cash payouts)
- **Target Issue**: https://github.com/tscircuit/core/issues/3521 (`Trace schDisplayLabel on branched connectivity becomes schematic_net_label`)
- **Pre-Submission Competition Audit**: `0` competing open PRs (`has_competing_open_pr("tscircuit/core", 3521) == False`)
- **Fork & Branch**: `pecopeko:fix/branched-trace-inline-display-label-3521` (`41ba5c6`)
- **Root Cause**: When branched trace connectivity (`>2` schematic ports without `<net>`) was converted solely into pairwise `directConnections`, `applyInlineNetLabelEligibility` skipped them due to `portsOnNet?.length === 2`, causing `schDisplayLabel` to fall back to `schematic_net_label` without `source_trace_id`. In composed subcircuits, `selectAll("trace")` also stopped at child `<subcircuit>` boundaries when resolving trace ownership.
- **Fix Summary**:
  - Updated `createSchematicTraceSolverInputProblem.ts` to emit an internal-flagged `netConnections` entry for routable, non-ground 3+ port trace networks where at least one `Trace` explicitly sets `schDisplayLabel` (stripped at solver boundary).
  - Updated `applyInlineNetLabelEligibility.ts` to allow `isBranchedTraceConnection` eligibility alongside explicit port-to-net traces.
  - Updated `applyInlineNetLabelPlacements.ts` to index `Trace` components across child subcircuits via `getDescendants()` and match `schDisplayLabel` / `displayName` / `name` / `mspPairId` when assigning `source_trace_id`.
  - Added regression coverage in `tests/features/schematic-inline-net-label/inline-net-label7.test.tsx` and updated `tests/repros/__snapshots__/repro126-trace-overlap-box-resistor-schematic.snap.svg` (where `<trace schDisplayLabel="FB" />` branches to `R1` and `R2`).
- **Local Verification (100% Pass After Final Edit)**:
  - `./node_modules/.bin/biome check` on touched files: **Checked 4 files, 0 issues**
  - `bun test --timeout 30000 tests/features/schematic-inline-net-label/inline-net-label7.test.tsx tests/repros/repro-tb67s579ftg-inline-label-attachments.test.tsx tests/repros/repro-tb67s579ftg-inline-net-labels.test.tsx tests/repros/repro-tb67s579ftg-vertical-inline-label-stub.test.tsx tests/repros/repro126-trace-overlap-box-resistor.test.tsx`: **6 pass, 0 fail** (78 `expect()` calls)
  - `NODE_OPTIONS="--max-old-space-size=3584" ./node_modules/.bin/tsc --noEmit`: **exit 0**

### 5. `tscircuit/tscircuit#6430` -> [PR #1038](https://github.com/tscircuit/props/pull/1038) (Open)
- **Repository**: `tscircuit/props` (eligible for `tscircuit/contribution-tracker` weekly GitHub Sponsors cash payouts)
- **Target Issue**: https://github.com/tscircuit/tscircuit/issues/6430 (`<keepout>` cannot block traces without also removing copper pour — `Part of tscircuit/tscircuit#6430`, aligned with `tscircuit/circuit-json#1015`)
- **Pre-Submission Competition Audit**: `0` competing open PRs in `tscircuit/props`
- **Fork & Branch**: `pecopeko:feat/keepout-allow-copper-pour-6430` (`fbff781`)
- **Fix Summary**:
  - Added optional boolean `allowCopperPour` prop to both `"circle"` and `"rect"` keepout variants in `lib/components/pcb-keepout.ts`, clarifying JSDoc on `allowTraces` and `allowPlacements`.
  - Expanded `tests/pcb-keepout-permissions.test.ts` permission & invalid-type coverage to include `allowCopperPour` across all shapes.
  - Regenerated `generated/COMPONENT_TYPES.md` via `bun run generate:component-types`.
- **Local Verification (100% Pass Before Opening PR)**:
  - `bun run format:check`: **Checked 442 files, 0 issues**
  - `bun run typecheck`: **exit 0**
  - `bun run check-circular-deps`: **No circular dependency found** (230 files)
  - `bun test`: **788 pass, 0 fail** (8 snapshots, 3713 `expect()` calls, 204 files)

## Honeypot & Non-Cash Orgs Excluded During Discovery
- Blocklisted AI-honeypot / duplicate synthetic orgs: `SecureBananaLabs`, `UnsafeLabs`, `ClankerNation`, `IES-BoilerRoom`, `zhangjiayang6835-cyber`
- Flagged non-cash credit-only org: `hanzoai` (rewards in platform credits rather than cash)
- Skipped contested `tscircuit` issues that already had open competing PRs (`tscircuit/jlcsearch#653`, `tscircuit/circuit-json-to-spice#73`, `tscircuit/core#6066`)
