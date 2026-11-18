# Live Solidity Audit Competition & Safe-Harbor Scan Triage

Deterministic static vulnerability pre-screen produced by `src/makemoney/scouts/solidity_audit_scanner.py` (interfaces & ERC721 transfers filtered, `.call` return bool checks inspected across 6 lines; candidates still require manual economic/PoC validation before reporting).

## Repository: `https://github.com/sherlock-audit/2026-07-tare.git`
- Non-test/non-interface `.sol` files scanned: `22`
- Candidate pattern hits: `5`

| Rule ID | Severity | File | Line | Snippet |
|---|---|---|---:|---|
| `SOL-FOT-04` | Low/Medium | `tare-io__tare-contracts/contracts/LoansExchange.sol` | 125 | `CURRENCY.safeTransferFrom(msg.sender, seller, uint256(price));` |
| `SOL-FOT-04` | Low/Medium | `tare-io__tare-contracts/contracts/LoansLedger.sol` | 252 | `currency.safeTransferFrom(addr, address(this), uint256(int256(amount)));` |
| `SOL-FOT-04` | Low/Medium | `tare-io__tare-contracts/contracts/PortfolioVault.sol` | 612 | `assetToken.safeTransferFrom(owner, address(this), assets);` |
| `SOL-FOT-04` | Low/Medium | `tare-io__tare-contracts/contracts/PortfolioVault.sol` | 738 | `IERC20(address(shareToken)).safeTransferFrom(owner, address(this), shares);` |
| `SOL-FOT-04` | Low/Medium | `tare-io__tare-contracts/contracts/TrustedSpender.sol` | 98 | `IERC20(token).safeTransferFrom(from, to, amount);` |

## Repository: `https://github.com/Cyfrin/battlechain-safe-harbor-contracts.git`
- Non-test/non-interface `.sol` files scanned: `27`
- Candidate pattern hits: `5`

| Rule ID | Severity | File | Line | Snippet |
|---|---|---|---:|---|
| `SOL-FOT-04` | Low/Medium | `src/BondManager.sol` | 211 | `s_bondToken.safeTransferFrom(payer, s_treasury, fee);` |
| `SOL-FOT-04` | Low/Medium | `src/BondManager.sol` | 214 | `s_bondToken.safeTransferFrom(payer, address(this), bondAmount);` |
| `SOL-CALL-05` | Medium | `src/CreateX.sol` | 251 | `(bool success, bytes memory returnData) = proxy.call{ value: msg.value }(data);` |
| `SOL-CALL-05` | Medium | `src/CreateX.sol` | 569 | `(bool success, bytes memory returnData) = proxy.call{ value: msg.value }(data);` |
| `SOL-CALL-05` | Medium | `src/CreateX.sol` | 688 | `(bool success,) = proxy.call{ value: msg.value }(initCode);` |

## Repository: `https://github.com/code-423n4/2026-04-monetrix.git`
- Non-test/non-interface `.sol` files scanned: `15`
- Candidate pattern hits: `5`

| Rule ID | Severity | File | Line | Snippet |
|---|---|---|---:|---|
| `SOL-FOT-04` | Low/Medium | `src/core/InsuranceFund.sol` | 40 | `usdc.safeTransferFrom(msg.sender, address(this), amount);` |
| `SOL-FOT-04` | Low/Medium | `src/core/MonetrixVault.sol` | 178 | `usdc.safeTransferFrom(msg.sender, address(this), amount);` |
| `SOL-FOT-04` | Low/Medium | `src/core/MonetrixVault.sol` | 185 | `IERC20(address(usdm)).safeTransferFrom(msg.sender, address(this), usdmAmount);` |
| `SOL-FOT-04` | Low/Medium | `src/tokens/sUSDM.sol` | 240 | `IERC20(asset()).safeTransferFrom(msg.sender, address(this), usdmAmount);` |
| `SOL-FOT-04` | Low/Medium | `src/tokens/sUSDMEscrow.sol` | 34 | `usdm.safeTransferFrom(sUSDM, address(this), amount);` |

## Repository: `https://github.com/sherlock-audit/2025-07-malda.git`
- Non-test/non-interface `.sol` files scanned: `105`
- Candidate pattern hits: `6`

| Rule ID | Severity | File | Line | Snippet |
|---|---|---|---:|---|
| `SOL-PRECISION-01` | Medium | `malda-lending/src/interest/JumpRateModelV4.sol` | 182 | `multiplierPerBlock = multiplierPerYear * 1e18 / (blocksPerYear * kink_);` |
| `SOL-FOT-04` | Low/Medium | `malda-lending/src/mToken/extension/mTokenGateway.sol` | 237 | `IERC20(underlying).safeTransferFrom(msg.sender, address(this), amount);` |
| `SOL-ORACLE-03` | High | `malda-lending/src/oracles/ChainlinkOracle.sol` | 81 | `) = priceFeeds[symbol].latestRoundData();` |
| `SOL-ORACLE-03` | High | `malda-lending/src/oracles/MixedPriceOracleV4.sol` | 138 | `(, int256 apiV3Price,, uint256 apiV3UpdatedAt,) = IDefaultAdapter(config.api3Feed).latestRoundData();` |
| `SOL-ORACLE-03` | High | `malda-lending/src/oracles/MixedPriceOracleV4.sol` | 139 | `(, int256 eOraclePrice,, uint256 eOracleUpdatedAt,) = IDefaultAdapter(config.eOracleFeed).latestRoundData();` |
| `SOL-FOT-04` | Low/Medium | `malda-lending/src/rebalancer/bridges/AcrossBridge.sol` | 120 | `IERC20(_token).safeTransferFrom(msg.sender, address(this), msgData.inputAmount);` |

## Repository: `https://github.com/sherlock-audit/2025-06-notional-exponent.git`
- Non-test/non-interface `.sol` files scanned: `35`
- Candidate pattern hits: `8`

| Rule ID | Severity | File | Line | Snippet |
|---|---|---|---:|---|
| `SOL-FOT-04` | Low/Medium | `notional-v4/src/AbstractYieldStrategy.sol` | 198 | `ERC20(asset).safeTransferFrom(t_CurrentLendingRouter, address(this), assetAmount);` |
| `SOL-ORACLE-03` | High | `notional-v4/src/oracles/AbstractCustomOracle.sol` | 45 | `) = sequencerUptimeOracle.latestRoundData();` |
| `SOL-PRECISION-01` | Medium | `notional-v4/src/oracles/Curve2TokenOracle.sol` | 79 | `) * primaryPrecision * DEFAULT_PRECISION / (dyAmount * secondaryPrecision);` |
| `SOL-ORACLE-03` | High | `notional-v4/src/oracles/Curve2TokenOracle.sol` | 101 | `) = baseToUSDOracle.latestRoundData();` |
| `SOL-ORACLE-03` | High | `notional-v4/src/oracles/PendlePTOracle.sol` | 82 | `) = baseToUSDOracle.latestRoundData();` |
| `SOL-FOT-04` | Low/Medium | `notional-v4/src/routers/AbstractLendingRouter.sol` | 93 | `ERC20(asset).safeTransferFrom(msg.sender, address(this), depositAssetAmount);` |
| `SOL-FOT-04` | Low/Medium | `notional-v4/src/routers/MorphoLendingRouter.sol` | 224 | `ERC20(asset).safeTransferFrom(receiver, address(this), assetToRepay);` |
| `SOL-FOT-04` | Low/Medium | `notional-v4/src/withdraws/AbstractWithdrawRequestManager.sol` | 107 | `ERC20(YIELD_TOKEN).safeTransferFrom(msg.sender, address(this), yieldTokenAmount);` |
