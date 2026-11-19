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

### 6. `tscircuit/tscircuit#6096` -> [PR #5697](https://github.com/tscircuit/core/pull/5697) (Open)
- **Repository**: `tscircuit/core` (eligible for `tscircuit/contribution-tracker` weekly GitHub Sponsors cash payouts)
- **Target Issue**: https://github.com/tscircuit/tscircuit/issues/6096 (`Schematic section auto-layout overflows sheet horizontally even when vertical space is available`)
- **Pre-Submission Competition Audit**: `0` competing open PRs (`has_competing_open_pr("tscircuit/tscircuit", 6096) == False` and `has_competing_open_pr("tscircuit/core", 6096) == False`)
- **Fork & Branch**: `pecopeko:fix/schematic-section-row-sheet-wrap-6096` (`649edaf`)
- **Root Cause**: `computeSchematicSectionLayoutUsingRows` wrapped rows purely at `targetRowWidth = Math.sqrt(totalArea) * 2` without clamping to the enclosing `<schematicsheet>` drawable content width, causing A4 sheets with multiple auto-laid-out sections to overflow horizontally and trigger `schematic_element_outside_sheet_warning`.
- **Fix Summary**:
  - Exported `SCHEMATIC_UNIT_TO_MM`, `SCHEMATIC_SHEET_INNER_MARGIN`, and `getSchematicSheetContentSize` in `lib/utils/schematic/warn-if-schematic-elements-outside-sheet.ts`.
  - Added optional `maxRowWidth?: number` parameter to `computeSchematicSectionLayoutUsingRows` (`effectiveMaxRowWidth = Math.min(targetRowWidth, maxRowWidth)` when defined). Circuits without an enclosing single sheet remain 100% unchanged.
  - Resolved the single shared `schematic_sheet_id` across unanchored sections in `lib/components/primitive-components/Group/Group_doInitialSchematicLayoutSections.ts` and passed its `getSchematicSheetContentSize` width as `maxRowWidth`.
  - Added regression coverage in `tests/features/schematic-sheet/schematic-sheet-section-row-wrap.test.tsx`.
- **Local Verification (100% Pass Before Opening PR)**:
  - `./node_modules/.bin/biome check` (4 touched/added files): **Checked 4 files, 0 issues**
  - `bun test --timeout 90000 tests/features/schematic-sheet/schematic-sheet-section-row-wrap.test.tsx tests/features/schematic-sheet/schematic-sheet-outside-warning.test.tsx tests/features/schematic-sheet/schematic-sheet-sections.test.tsx`: **4 pass, 0 fail** (16 `expect()` calls)
  - `NODE_OPTIONS="--max-old-space-size=3584" ./node_modules/.bin/tsc --noEmit`: **exit 0**

### 7. `tscircuit/cli#5767` -> [PR #5861](https://github.com/tscircuit/cli/pull/5861) (Open)
- **Repository**: `tscircuit/cli` (eligible for `tscircuit/contribution-tracker` weekly GitHub Sponsors cash payouts)
- **Target Issue**: https://github.com/tscircuit/cli/issues/5767 (`@tscircuit/cli 0.1.2452 bundles brace-expansion 2.0.1 and minimatch 5.1.2 (via make-vfs), both with published advisories`)
- **Pre-Submission Competition Audit**: `0` competing open PRs (`has_competing_open_pr("tscircuit/cli", 5767, topic_terms=("make-vfs", "brace-expansion")) == False`)
- **Fork & Branch**: `pecopeko:fix/remove-bundled-make-vfs-advisories-5767` (`f91006b`)
- **Root Cause**: Direct (`lib/shared/generate-circuit-json.tsx`) and transitive (`winterspec` via `@tscircuit/file-server`) imports of `make-vfs` pulled inlined copies of `glob-promise -> glob 8 -> minimatch 5.1.2 -> brace-expansion 2.0.1` into all 4 published `dist/` bundles.
- **Fix Summary**:
  - Replaced `make-vfs` with a zero-dependency Node `fs/promises` + `path` module in `lib/shared/make-vfs.ts`.
  - Switched `lib/shared/generate-circuit-json.tsx` to `./make-vfs`, removed `"make-vfs"` from `devDependencies` (`package.json` + `bun.lock`), and added a `Bun.build` `onResolve(/^make-vfs$/)` plugin in `scripts/bun-build.ts` so transitive `winterspec` imports resolve to the internal helper.
  - Added regression & bundle-hygiene tests in `tests/cli/make-vfs-bundle-hygiene.test.ts` verifying `0` occurrences of `node_modules/make-vfs`, `brace-expansion`, and `minimatch` across all 4 `dist/` artifacts.
- **Local Verification (100% Pass Before Opening PR)**:
  - `bun run build`: **4 bundles built cleanly, all grep counts = `0` for `node_modules/make-vfs`, `brace-expansion`, `minimatch`**
  - `bun run format:check`: **Checked 648 files, 0 issues**
  - `bun scripts/check-for-dependencies.ts`: **exit 0**
  - `NODE_OPTIONS="--max-old-space-size=3584" ./node_modules/.bin/tsc --noEmit`: **exit 0**
  - `bun test --timeout 45000 tests/cli/make-vfs-bundle-hygiene.test.ts tests/cli/export/export-output-path.test.ts tests/cli/build/build.test.ts`: **17 pass, 0 fail** (103 `expect()` calls)

### 8. `tscircuit/core#3520` -> [PR #5704](https://github.com/tscircuit/core/pull/5704) (Open)
- **Repository**: `tscircuit/core` (eligible for `tscircuit/contribution-tracker` weekly GitHub Sponsors cash payouts)
- **Target Issue**: https://github.com/tscircuit/core/issues/3520 (`schematicsymbol schRotation is ignored for oriented native symbols`)
- **Pre-Submission Competition Audit**: `0` competing open PRs (`has_competing_open_pr("tscircuit/core", 3520, max_pages=4) == False`)
- **Fork & Branch**: `pecopeko:fix/schematic-symbol-oriented-rotation-3520` (`b1125be`)
- **Root Cause**: `PrimitiveComponent._getSchematicSymbolName()` remapped oriented native symbols such as `opamp_with_power_left` @ `schRotation={180}` onto `opamp_with_power_right`, which is mirrored across the X-axis in `schematic-symbols` (`inp1/+` remains upper-left instead of rotating geometrically to lower-left). Because `circuit-to-svg` matches `symbol_name` ports solely by unrotated angle, reusing mismatched `symbol_name` drops the requested 180° rotation.
- **Fix Summary**:
  - Added `lib/components/primitive-components/SchematicSymbol/getSchematicSymbolWithRotation.ts` to verify whether rotated port and static-label offsets align with `resolvedSymbol`, keeping `mode: "native"` for unrotated symbols, matching library rotations (`opamp_with_power_right` @ `90` -> `opamp_with_power_up`), and `_horz`/`_vert` quarter-turns.
  - Otherwise geometrically rotates the raw `SchSymbol` (`primitives`, `ports`, `size`, and 9-point text anchors CCW) around `symbol.center` and materializes Circuit JSON schematic primitives with `is_box_with_pins: false`.
  - Updated `SchematicSymbol.ts` and `SchematicSymbol_doInitialSchematicComponentRender.ts` and added regression tests + snapshot in `tests/components/primitive-components/schematic-symbol-oriented-rotation.test.tsx`.
- **Local Verification (100% Pass Before Opening PR)**:
  - `./node_modules/.bin/biome check lib/components/primitive-components/SchematicSymbol/ tests/components/primitive-components/schematic-symbol-oriented-rotation.test.tsx`: **Checked 5 files, 0 issues**
  - `bun test --timeout 90000 tests/components/primitive-components/schematic-symbol-oriented-rotation.test.tsx tests/components/primitive-components/schematic-symbol-element.test.tsx tests/components/primitive-components/schematic-symbol-schRotation.test.tsx tests/components/primitive-components/schematic-symbol-two-sheets-mosfet-opamp.test.tsx tests/components/primitive-components/schematic-symbol-connections-mosfet.test.tsx tests/components/primitive-components/schematic-symbol-speaker.test.tsx`: **7 pass, 0 fail** (21 `expect()` calls)
  - `NODE_OPTIONS="--max-old-space-size=3584" ./node_modules/.bin/tsc --noEmit`: **exit 0**

## Honeypot & Non-Cash Orgs Excluded During Discovery
- Blocklisted AI-honeypot / duplicate synthetic orgs: `SecureBananaLabs`, `UnsafeLabs`, `ClankerNation`, `IES-BoilerRoom`, `zhangjiayang6835-cyber`, `WholeTroutMedia`, `relayhop`, `limitlessprojects`
- Flagged non-cash credit-only orgs: `hanzoai` (platform credits), `zoo-apps` (non-cash rewards), `CaravanaCloud` (stale un-funded hack/non-cash issues)
- Skipped contested `tscircuit` issues that already had open competing PRs (`tscircuit/jlcsearch#653`, `tscircuit/circuit-json-to-spice#73`, `tscircuit/core#6066`), filtered numeric-owner, Algora webhook test sandbox repos (`_NUMERIC_OWNER_RE`, `_SANDBOX_REPO_NAME_RE`), points-only reward labels (`points:50` -> `non_cash_only`), and off-topic/meta project-update threads, and multi-page PR + cross-repo `/timeline` scans across `110+` `tscircuit` repos verified `0` new uncontested bug candidates in Iterations 5–10.
