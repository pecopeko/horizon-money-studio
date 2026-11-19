# Immunefi Live Security Audit Dossier — November 2026

**Auditor**: Auditor A1 — Deep Solidity Security Researcher  
**Audit Date**: 2026-11-20  
**Methodology**: Line-by-line manual static source-code audit (call chains, assembly, fixed-point arithmetic bounds, state-machine invariants, storage/transient-storage layouts, cross-contract trust boundaries). No exploit scripts or weaponized payloads generated; purely defensive vulnerability discovery, invariant verification, and patch design. (`forge`/`solc` not installed locally.)

---

## Executive Summary & Verdict Table

| Target Program | Repository & Commit | Scope Read (LOC) | Prior Audits Noted in Repo | Critical / High / Medium | Confirmed Low / Info | Overall Verdict |
|---|---|---:|---|---:|---:|---|
| **Base Everest** (Imminent Immunefi Comp) | `immunefi-team/audit-comp-base-everest-nitro-validator` (`0ea0d123`) | 3,359 LOC (100%) | 2 Cantina audits (through Aug 2026) | **0** | **3** (1 Low, 2 Info) | **CLEAN (No High/Crit)** — Hardened post-Cantina; 1 real `uint8` overflow edge case in GeneralizedTime (years `>= 2300` / pre-2000) + 2 defensive hardening items |
| **Base Everest** (Imminent Immunefi Comp) | `immunefi-team/audit-comp-base-everest-contracts` (`b9b76d97`) | 21,924 LOC repo; all multiproof/TEE/ZK/Dynamic Upgrades/200ms/bridge core read | 8 Cantina audits (Mar–Oct 2026) | **0** | **1** (+1 legacy OOS note) | **CLEAN (No High/Crit)** — Multiproof, TEE/ZK verification, 200ms cadence, and `ProtocolVersions` hash-chain invariants hold |
| **Metricxyz** (Live `$500k` Immunefi Bounty) | `Metricxyz/oracle-contracts` (`7525bbd6`), `Metricxyz/pool-contracts` (`ddf8ae0c`), `Metricxyz/periphery-contracts` (`5ceaec32`) | 14,476 LOC (100% core/oracle/periphery) | Zellic (Jun & Sep 2026), Sherlock collab/contest/update (May–Sep 2026) | **0** | **3** (Low/Info) | **CLEAN (No High/Crit)** — All fund-loss, share-inflation, oracle-manipulation, overflow, and callback-reentrancy vectors ruled out against full call chains |

> **Honest Submission Recommendation**: **DO NOT submit any Critical/High/Medium report from these 5 repositories** as currently audited. None of the minor Low/Informational findings below meet Immunefi's Medium/High/Critical payout thresholds (typically requiring direct theft/freezing of funds, insolvency, or protocol halt), and submitting Low/Info items risks spam penalties or invalidation. If participating in the Base Everest Audit Competition (which may include Low/QA categories), Findings **BE-L1** and **BE-I1** are genuine, verified code defects suitable only for Low/QA tiers.

---

## Target 1A: `audit-comp-base-everest-nitro-validator`

- **Repository**: `https://github.com/immunefi-team/audit-comp-base-everest-nitro-validator`
- **Audited Commit**: `0ea0d12366b4fa44f9e07e4755f2ad36561cb674` (`docs: add 2026 Cantina audit report (#81)`)
- **Files Audited (100%, 3,359 LOC)**: `NitroValidator.sol`, `CertManager.sol`, `CborDecode.sol`, `Asn1Decode.sol`, `LibBytes.sol`, `P384Verifier.sol`, `ECDSA384Curve.sol`, `Sha2Ext.sol`, `vendor/ECDSA384.sol`, `vendor/MemoryUtils.sol`.

### Confirmed Findings

#### [BE-L1] CONFIRMED — LOW: `uint8` Arithmetic Overflow in `Asn1Decode.timestampAt` for GeneralizedTime Years with Hundreds Digit `>= 3`
- **Location**: `src/Asn1Decode.sol#L241-L248`
- **Root Cause**:
  ```solidity
  uint16 _years;
  if (length == 13) {
      _years = (uint8(der[offset]) - 48 < 5) ? 2000 : 1900;
  } else {
      _years = (uint8(der[offset]) - 48) * 1000 + (uint8(der[offset + 1]) - 48) * 100;
      offset += 2;
  }
  ```
  In Solidity `^0.8.15` (compiled with `solc 0.8.26`), `(uint8(der[offset + 1]) - 48)` has type `uint8`, and the integer literal `100` fits in `uint8`. Consequently, `(uint8(der[offset + 1]) - 48) * 100` is evaluated in `uint8` arithmetic before widening to `uint16`. Whenever the hundreds digit is `3` through `9` (e.g., `19991231235959Z` in GeneralizedTime or any certificate valid in year `2300+` such as `23000101000000Z`), `digit * 100 >= 300 > 255`, triggering a checked arithmetic overflow (`Panic(0x11)`).
- **Impact**: Low / QA. Under RFC 5280 §4.1.2.5, years 1970–2049 use UTCTime (`length == 13`, unaffected) and GeneralizedTime (`length == 15`) starts in 2050. Years 2050–2299 have hundreds digits `0, 1, 2` (`<= 200 <= 255`, unaffected). Only GeneralizedTime timestamps in 1970–1999 (non-standard) or `>= 2300` revert unexpectedly with `Panic(0x11)`.
- **Recommended Patch**:
  ```diff
  - _years = (uint8(der[offset]) - 48) * 1000 + (uint8(der[offset + 1]) - 48) * 100;
  + _years = uint16(uint8(der[offset]) - 48) * 1000 + uint16(uint8(der[offset + 1]) - 48) * 100;
  ```

#### [BE-I1] CONFIRMED — INFORMATIONAL: Null Pointer Dereference into Solidity Scratch Space `0x00..0x3f` When `_doubleScalarMultiplication` Returns Point at Infinity
- **Location**: `src/vendor/ECDSA384.sol#L166-L179`, `L699-L712`
- **Root Cause**:
  `ECDSA384` represents the elliptic curve point at infinity as the null memory pointer pair `(0, 0)`. In `_verify`, the return value `scalar1` from `_doubleScalarMultiplication(...)` is passed directly to `U384.modAssign(call, scalar1, params_.n)` and `U384.eq(scalar1, inputs_.r)` without checking `if (scalar1 == 0)`. When `u1*G + u2*Q = O`, `modAssign` reads `mload(0x00)` and `mload(0x20)` (Solidity's scratch space), reduces those bytes modulo `n`, overwrites `0x00..0x3f`, and compares the result to `inputs_.r`.
- **Why Ruled Out as Medium/High/Critical**:
  1. `P384Verifier` is a standalone contract called via external call; nothing inside `P384Verifier` or `ECDSA384` writes to scratch space `0x00..0x3f`, so `mload(0x00)` and `mload(0x20)` are strictly `0`. Since line 119 rejects `r == 0`, `U384.eq(0, inputs_.r)` always evaluates to `false`.
  2. Reaching `u1*G + u2*Q = O` for a legitimate AWS public key `Q = d*G` requires `z + r*d ≡ 0 (mod n)`, which is equivalent to recovering the private key `d` (ECDLP).
  3. Still a real memory-safety hazard for any third-party library consumer invoking `ECDSA384.verifyWithHints` internally after dirtying scratch space `0x00..0x3f`.
- **Recommended Patch**:
  ```solidity
  if (scalar1 == 0) {
      return (false, U384.hintCursor(call));
  }
  U384.modAssign(call, scalar1, params_.n);
  ```

#### [BE-I2] CONFIRMED — INFORMATIONAL: `NitroValidator._parseAttestation` Omitted Optional Keys Leave `isNull() == false` & `decodeAttestationTbs` Skips Outer `0x84` Check
- **Locations**: `src/NitroValidator.sol#L71-L75`, `L137-L143`
- **Details**:
  - If `"user_data"` or `"nonce"` is omitted from the CBOR map (rather than present with CBOR `null` `0xf6`), the zero-initialized `CborElement(0)` has `cborType() == 0x00`, so `.isNull()` returns `false` while `.length()` returns `0` (whereas `publicKey` on line 138 explicitly handles `CborElement.unwrap(ptrs.publicKey) == 0`).
  - `decodeAttestationTbs` does not verify that `attestation[offset - 1] == 0x84` (COSE_Sign1 4-element array). Safe on-chain because `validateAttestationWithHints` enforces `ATTESTATION_TBS_PREFIX` and verifies the P-384 signature.
- **Recommended Patch**: Initialize `ptrs.publicKey`, `ptrs.userData`, and `ptrs.nonce` to the CBOR null sentinel `LibCborElement.toCborElement(0xf6, 0, 0)` (mirroring `_newPcrBank()`), and `require(attestation[offset - 1] == 0x84, "invalid COSE_Sign1 array")` in `decodeAttestationTbs`.

### Verified Security Invariants & Ruled-Out Hypotheses (`nitro-validator`)
- **Unchecked `pop(staticcall(gas(), 0x5, ...))` in `ECDSA384.sol` (FALSE-POSITIVE-RULED-OUT)**: In `P384Verifier`, only `verifyP384SignatureWithHints` is exposed; every `modexp` precompile call uses exponent `1`, `2`, or `3` (cost `<= 500` gas post-Fusaka EIP-7883). Under EIP-150's 63/64 rule, if any `modexp` subcall runs out of gas, at most `500 / 63 ≈ 7` gas remains in the parent frame — insufficient to execute even the final `U384.eq` + `hintCursor` + `require` return sequence. Cannot forge verification via gas griefing.
- **Unreduced 384-bit Inverse Hints & `_mul` Overflow (`ECDSA384.sol:871-969, 1054-1119`) (FALSE-POSITIVE-RULED-OUT)**: Although `_nextInverseHint` does not bound `inv_ < p` (or `< n`), every hint is checked via `b * inv ≡ 1 (mod m)` and immediately multiplied and reduced modulo `m`. Worst-case `_mul` for `a = b = 2^384 - 1` produces top limb `r1 = 2^256 - 1` (zero overflow across all 6 intermediate limbs).
- **`CertManager._loadVerified` Dirty High-Order Bits (`CertManager.sol:648-661`) (FALSE-POSITIVE-RULED-OUT)**: Although `mload(add(packed, 0x1 / 0x9 / 0x11))` leaves preceding length/field bytes in upper stack bits of `ca`, `notAfter`, and `maxPathLen`, `solc 0.8.26` emits type cleanup (`and(0xff)`, `signextend(7, ...)`) before comparisons and memory-struct operations.
- **Certificate Chain, Revocation & Root Pinning (`CertManager.sol`) (VERIFIED)**: Non-root cache keys hash `tbsCertificate` (immune to ECDSA malleability); revocation keys use `keccak256(issuerHash, serialHash)` from CA-signed TBS; `_isPinnedRootAlias` blocks malleated self-signed root twins; `_requireCachedChainValid` walks every ancestor to `ROOT_CA_CERT_HASH` verifying both revocation and expiry; `maxPathLen`, `BasicConstraints`, `KeyUsage` (`0x04` CA / `0x80` leaf), and unsupported critical extensions are strictly enforced; `verifiedParent` cannot form cycles.
- **CBOR Parser (`NitroValidator.sol`, `CborDecode.sol`) (VERIFIED)**: Bitmask prevents duplicate top-level keys; `MAX_PCRS = 32`, `MAX_CABUNDLE_CERTS = 32`, `MAX_CBOR_DEPTH = 64` prevent OOM/recursion DoS; odd indefinite maps and trailing bytes are rejected; `Sha2Ext.sha384` IVs, padding, and round functions match FIPS 180-4.

---

## Target 1B: `audit-comp-base-everest-contracts`

- **Repository**: `https://github.com/immunefi-team/audit-comp-base-everest-contracts`
- **Audited Commit**: `b9b76d97dca3c420098f597ebc65bee4f28001b7` (`add legacy nft interface ids for the bridge (#458)`)
- **Primary Contracts Audited**: `AggregateVerifier.sol`, `TEEProverRegistry.sol`, `TEEVerifier.sol`, `ZKVerifier.sol`, `Verifier.sol`, `AnchorStateRegistry.sol`, `DisputeGameFactory.sol`, `DelayedWETH.sol`, `ProtocolVersions.sol`, `BaseTime.sol`, `OptimismPortal2.sol`, `L1ERC721Bridge.sol`, `L2ERC721Bridge.sol`, `FeeDisburser.sol`, `BalanceTracker.sol`, `L1Block.sol`, `OwnableManagedUpgradeable.sol`.

### Confirmed Observations

#### [BE-L2] CONFIRMED — LOW / DESIGN EDGE: `AggregateVerifier.resolve()` Extends Resolution Delay by 5 Days When `TEE_VERIFIER` Is Nullified on a ZK-Challenged Game
- **Location**: `src/L1/proofs/AggregateVerifier.sol#L553-L567`, `L937-L947`
- **Root Cause**:
  When a game initialized with a bad TEE proof has been validly challenged with a ZK proof (`proofCount == 2`, `counteredByIntermediateRootIndexPlusOne > 0`, `expectedResolution = t_challenge + 5 days`), and `TEE_VERIFIER` is subsequently nullified before `resolve()` is called:
  1. Once `gameOver()` becomes true, calling `resolve()` invokes `_updateProofCount()`.
  2. Line 938 matches `proofTypeToProver[ProofType.TEE] != address(0) && TEE_VERIFIER.nullified()`, calls `_proofRefutedUpdate(ProofType.TEE)` (decrementing `proofCount` `2 -> 1` and calling `_increaseExpectedResolution()`, resetting `expectedResolution = block.timestamp + SLOW_FINALIZATION_DELAY`), and returns `GameStatus.IN_PROGRESS`.
  3. The ZK challenger must wait an additional 5 days before calling `resolve()` a second time to finalize `CHALLENGER_WINS` and unlock their bond reward, even though the TEE nullification *confirmed* rather than weakened the ZK challenge.
- **Impact**: Low (temporary 5-day delay on challenger bond claim under simultaneous challenge + verifier nullification; no fund loss, no invalid state resolution).
- **Recommended Patch**: In `_proofRefutedUpdate(ProofType.TEE)`, skip `_increaseExpectedResolution()` when `counteredByIntermediateRootIndexPlusOne > 0` (the ZK challenge already set `expectedResolution` to `t_challenge + SLOW_FINALIZATION_DELAY`).

#### [OOS / LEGACY NOTE] `BalanceTracker.initialize` Lacks Access Control on `reinitializer(3)`
- **Location**: `src/L1/BalanceTracker.sol#L93-L98`
- **Status**: Legacy Base operations contract (non-Everest multiproof); standard atomic proxy-upgrade initialization pattern. Do not submit unless an uninitialized mainnet proxy exists.

### Verified Security Invariants & Ruled-Out Hypotheses (`base-everest-contracts`)
- **Cross-L1-Head Conflicting Proof Hypothesis (`AggregateVerifier.initializeWithInitData` vs `challenge`/`nullify`) (FALSE-POSITIVE-RULED-OUT)**: `initializeWithInitData` accepts an arbitrary canonical L1 origin within 8191 blocks (`blockhash` + EIP-2935), while `verifyProposalProof`/`challenge`/`nullify` use `l1Head()` (`blockhash(block.number - 1)`). Because `_verifyL1Origin` validates against the current canonical L1 chain, `l1Origin` is strictly an ancestor of `l1Head()`, and OP Stack safe-head derivation is monotonic under canonical L1 extension (an unposted batch before sequencing-window expiry halts derivation rather than emitting divergent blocks).
- **`TEEProverRegistry.registerSigner` Public-Key Overwrite DoS (FALSE-POSITIVE-RULED-OUT)**: Although AWS Nitro hypervisors do not enforce proof-of-possession on the enclave's `public_key` field, `registerSigner` is gated by `onlyOwnerOrManager`, preventing permissionless overwriting of `signerImageHash[honestEnclave]`.
- **200ms Block Cadence & `ProtocolVersions` Hash-Chain Immutability (VERIFIED)**: `_firstFastBlock()` uses `divUp(fastActivationTimestamp - L2_GENESIS_TIMESTAMP, L2_BLOCK_TIME)`, matching OP Stack hardfork activation semantics for both even and odd `(T_act - T_0)` offsets. `MIN_NOTICE = 1 hour`, `FREEZE_WINDOW = 1 hour`, and `_assertNoScheduledSuccessor` guarantee that no initialized game's `scheduleId` or `_intervalsAt(startingBlock)` selection can ever shift post-initialization.
- **CWIA Layout Enforcement (VERIFIED)**: Exact `calldatasize()` verification (`0x8E + 0x20 * N + 0x40 + ceil32(proof.length)`) prevents extra-data UUID spoofing and fails closed if `gameArgs` is ever accidentally populated.

---

## Target 2: Metricxyz LIVE `$500,000` Immunefi Bug Bounty

- **Repositories & Audited Commits**:
  - `Metricxyz/oracle-contracts`: `7525bbd6b536bcd0c283de18af256fe54d629456` (4,449 LOC — 100% read)
  - `Metricxyz/pool-contracts`: `ddf8ae0cdb2ad0041c3ff3aebc200cf488d5b0d3` (5,681 LOC — 100% read)
  - `Metricxyz/periphery-contracts`: `5ceaec32a4a8ceb5fe1411ec1bc5d5f9aef32647` (4,346 LOC — 100% read)

### Confirmed Low / Informational Findings (Not Bounty-Eligible)

#### [MET-I1] CONFIRMED — INFORMATIONAL: `MetricOmmSimpleRouter` Leaves `TransientCallbackPool` Populated During Outer Pool's `afterSwap` Hook
- **Location**: `periphery-contracts/contracts/MetricOmmSimpleRouter.sol#L106, L145, L172, L212, L217-L239`
- **Details**:
  `_justPayCallback` and the `tradesLeft == 0` branch of `_exactOutputIterateCallback` pay the input token without clearing `TransientCallbackPool`. Consequently, in a multi-hop `exactOutput` swap (`[pool0, pool1]`), `pool0` has already exited its reentrancy guard while `pool1._afterSwap(...)` runs with `TransientCallbackPool` still holding `(expectedPool = pool0, tradesLeft = 0, payer = user, tokenToPay = tokens[0])`.
- **Why Ruled Out as Medium/High/Critical**:
  `MetricOmmPool.swap` invokes `metricOmmSwapCallback` strictly on `msg.sender` (the caller of `pool0.swap`). Because `MetricOmmSimpleRouter.exactOutput` holds `nonReentrant` until completion, no untrusted extension on `pool1` can re-enter the router to trigger `pool0.swap` with `msg.sender == router`, and calling `pool0.swap` directly from the extension makes `pool0` call back the extension rather than the router.
- **Recommended Patch**: Call `_clearExpectedCallbackPool()` immediately inside `_justPayCallback` and inside the `tradesLeft == 0` branch of `_exactOutputIterateCallback` (matching `MetricOmmPoolLiquidityAdder.sol#L195`).

#### [MET-I2] CONFIRMED — INFORMATIONAL: `MetricOmmPoolLiquidityAdder.multicall` Omits `whenNotEntered` Modifier
- **Location**: `periphery-contracts/contracts/MetricOmmPoolLiquidityAdder.sol#L51-L56`
- **Details**:
  Unlike `MetricOmmSimpleRouter.multicall` (`MetricOmmSimpleRouter.sol#L52`), `MetricOmmPoolLiquidityAdder.multicall` does not enforce `whenNotEntered`.
- **Why Ruled Out as Medium/High/Critical**:
  Every state-changing method on `MetricOmmPoolLiquidityAdder` and `PeripheryPayments` is `nonReentrant` except `metricOmmModifyLiquidityCallback`, which strictly checks `msg.sender == expectedPool` (a factory-deployed `MetricOmmPool`). `delegatecall` in `multicall` preserves `msg.sender`, so no third-party extension or token callback can impersonate `expectedPool`.
- **Recommended Patch**: Add `whenNotEntered` to `MetricOmmPoolLiquidityAdder.multicall` for consistency with `MetricOmmSimpleRouter`.

#### [MET-I3] CONFIRMED — INFORMATIONAL: Zero-Width Effective Bin Division-by-Zero Panic in `SwapMath.buyToken1InBinSpecifiedIn` Under Extreme Low Price (`< 5.4e-14`)
- **Location**: `pool-contracts/contracts/libraries/SwapMath.sol#L734-L742`
- **Details**:
  If a synthetic/meme pair has `referencePriceX64 < 1e6` (price `< 5.4e-14`) and a bin has `lengthE6 == 1`, `distanceE6ToPriceX64` floors both bounds to the same integer (`effLowerX64 == effUpperX64`). When `priceLimitX64 > effLowerX64`, `buyToken1InBinSpecifiedIn` calls `calculateBinPositionAtPrice`, dividing by `upperEffPriceX64 - lowerEffPriceX64 == 0` (`Panic(0x12)`, fail-closed, no fund loss).

### Exhaustive Invariants Verified & False-Positive Vectors Ruled Out (Metricxyz)
1. **Pool Solvency & Fee Accounting (`MetricOmmPool.sol`, `LiquidityLib.sol`, `SignedMath.sol`, `FeeMath.sol`)**:
   - `balance * SCALE >= binTotals + notionalFee + pendingAdmin + pendingProtocol` holds monotonically: `addLiquidity` rounds up (`Ceil`), `removeLiquidity` rounds down (`Floor`), `swap` rounds input up (`SignedMath.ceilDiv` on positive delta) and output down (`SignedMath.ceilDiv` on negative delta truncates toward zero).
   - `collectFees` uses `trySafeTransfer`, preventing blacklisted admin/protocol fee receivers from DoS-ing fee collection or factory fee updates.
   - `setPoolAdminFees` and `_updatePoolProtocolFee` always invoke `_collectFees(pool, oldConfig)` before updating rates, preventing retroactive fee-split misattribution or stranded `notionalFeeToken*Scaled`.
2. **First-Depositor / Share-Inflation Attack (`LiquidityLib.sol`, `MetricOmmPoolFactory.sol`)**:
   - **Ruled out**: Direct ERC-20 donations never credit `binState` (captured as protocol/admin surplus). `addLiquidity` takes `shares` (strictly `>= minimalOperationalLiquidity >= 1e6 * 1e18 / min(P0, P1)`) and charges `ceil(balance * shares / totalShares)`, making 0-share minting impossible.
3. **Unchecked Arithmetic & Truncation Bounds (`SwapMath.sol`, `MetricOmmPool.sol`, `Packed.sol`)**:
   - **Ruled out**: `effUpperX64 <= 9.39 * 2^128` (even with extreme `ask / ref`, `ref` cancels). In `computeAnalyticalTargetPosForBuyToken0`, `Math.mulDiv(inputAmount << 128, 1 << 128, aX128)` overflow (`inputAmount >= aX128`) would require `upper / lower > 2^25`, whereas `HARD_MIN_BIN_DISTANCE_LIMIT_E6 = -999_999` and `uint16 lengthE6 <= 65_535` bound `upper / lower <= 2^16`. Any hypothetical `uint128` truncation in `platformFees.addBoth` forces `binTotals.scaledToken*` to exceed `2^128` and revert on `.toUint128()`.
   - **Post-audit change `d4d0e2a` (`_validateBidAskReferencePriceX64`)**: `numerator = (ref - bid) * ref < 2^256`, `denominator = bid * (ask - ref) < 2^256`, `M_X64 = 2^64 + (mX8 << 56) < 2^73`, `Ceil` rounding strictly conservative.
4. **Bin Position & Direction Invariants (`MetricOmmPool.sol`, `SwapMath.sol`, `LiquidityLib.sol`)**:
   - Bins `< curBinIdx` hold strictly `token1`; bins `> curBinIdx` hold strictly `token0`; `binCreditScaled >= 1` for every non-zero swap step (`totalFeeOfGrossX64 < ONE_X64`); partial bin fills never land on `0` (sell) or `MAX_POS_BIN` (buy); emptying `curBinIdx` resets `curPosInBin` consistently.
5. **Oracle Layer (`oracle-contracts`)**:
   - `AnchoredPriceProvider`: Synthetic interval division preserves `refBid <= refMid < refAsk` by construction; source call is gas-capped (`500_000`) and return-size-capped (`96` bytes) in memory-safe assembly; stale/zero/saturated (`65534`)/stalled (`65535`) feeds fail closed.
   - `OracleBase` & `MultiplierOracle`: `tx.origin == address(0)` off-chain bypass, `getSellAndBuyPrices()` sharing `PoolActions.SWAP`, and `register()` clearing pool blacklist are all explicitly documented design behaviors (providers/feeds are stopped via `setBlacklist(provider, true)`, `setFeedDisabled`, or `removeParamsAdapter`).
   - `CompressedOracleV1`: Storage slot layout `(creator << 96) | slotId` cannot collide with slots `0..5` (`creator != address(0)`) or mapping keccak slots (`2^-248`); `usedPusherDeadline` enforces single-use EIP-191 consent; `fallback()` handles `calldatasize() == 0` via `end % 32 != 0` revert.
   - `LazerConsumer` & `ChainlinkOracle`: All Yul bit-shifts, `KNOWN_PROP_SIZES = 0x9882000822888`, `FeedUpdateTimestamp` freshness, Chainlink V3/V4/HFS resolution-nibble fail-close, and `_spreadFromBidAsk` sign/overflow bounds verified exact.
6. **Periphery & Extensions (`periphery-contracts`)**:
   - `PeripheryPayments.pay` wraps `address(this).balance` (immune to `msg.value` reuse across `multicall` / `sequence`).
   - `ExternalSwap` & `ExternalSwapExecutor`: `payer` is either `msg.sender` or `address(this)` (never another user); `nonReentrant` blocks router reentrancy during arbitrary `executor.swap(params)`; refund uses exact balance increase during the call.
   - `OracleValueStopLossExtension` & `PriceVelocityGuardExtension`: Overflow bounds, timelock arithmetic (`uint256` checked before `uint40` cast), direction-aware drawdown triggers, and same-block anchor budget verified sound.
