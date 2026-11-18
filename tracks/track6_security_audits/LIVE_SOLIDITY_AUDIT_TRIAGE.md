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

## Repository: `https://github.com/sherlock-audit/2026-01-fluid-dex-v2.git`
- Non-test/non-interface `.sol` files scanned: `431`
- Candidate pattern hits: `42`

| Rule ID | Severity | File | Line | Snippet |
|---|---|---|---:|---|
| `SOL-ORACLE-03` | High | `fluid-contracts/contracts/oracle/cappedRates/chainlinkCappedRate.sol` | 12 | `(, int256 rate_, , , ) = IChainlinkAggregatorV3(_RATE_SOURCE).latestRoundData();` |
| `SOL-ORACLE-03` | High | `fluid-contracts/contracts/oracle/cappedRatesL2/chainlinkCappedRateL2.sol` | 16 | `(, int256 rate_, , , ) = IChainlinkAggregatorV3(_RATE_SOURCE).latestRoundData();` |
| `SOL-ORACLE-03` | High | `fluid-contracts/contracts/oracle/fluidCenterPriceL2.sol` | 64 | `(uint80 roundId_, , , , ) = _SEQUENCER_ORACLE.latestRoundData();` |
| `SOL-ORACLE-03` | High | `fluid-contracts/contracts/oracle/fluidCenterPriceL2.sol` | 137 | `(uint80 roundId_, int256 answer_, uint256 startedAt_, , ) = _SEQUENCER_ORACLE.latestRoundData();` |
| `SOL-ORACLE-03` | High | `fluid-contracts/contracts/oracle/fluidOracleL2.sol` | 47 | `(uint80 roundId_, , , , ) = _SEQUENCER_ORACLE.latestRoundData();` |
| `SOL-ORACLE-03` | High | `fluid-contracts/contracts/oracle/fluidOracleL2.sol` | 107 | `(uint80 roundId_, int256 answer_, uint256 startedAt_, , ) = _SEQUENCER_ORACLE.latestRoundData();` |
| `SOL-ORACLE-03` | High | `fluid-contracts/contracts/oracle/implementations/chainlinkOracleImpl.sol` | 150 | `try feed_.latestRoundData() returns (uint80, int256 exchangeRate_, uint256, uint256, uint80) {` |
| `SOL-PRECISION-01` | Medium | `fluid-contracts/contracts/oracle/implementations/dex/dexPricesAndExchangePrices.sol` | 544 | `p2_ = p2_ < 1e50 ? (p2_ * pb_) / 1e27 : (p2_ / 1e27) * pb_;` |
| `SOL-PRECISION-01` | Medium | `fluid-contracts/contracts/oracle/implementations/dex/dexSmartColOracleImpl.sol` | 20 | `? 1e18 / ((1e12 * TOKEN_0_DENOMINATOR_PRECISION) / TOKEN_0_NUMERATOR_PRECISION)` |
| `SOL-PRECISION-01` | Medium | `fluid-contracts/contracts/oracle/implementations/dex/dexSmartColOracleImpl.sol` | 21 | `: 1e18 / ((1e12 * TOKEN_1_DENOMINATOR_PRECISION) / TOKEN_1_NUMERATOR_PRECISION);` |
| `SOL-PRECISION-01` | Medium | `fluid-contracts/contracts/oracle/implementations/dex/dexSmartDebtOracleImpl.sol` | 20 | `? 1e18 / ((1e12 * TOKEN_0_DENOMINATOR_PRECISION) / TOKEN_0_NUMERATOR_PRECISION)` |
| `SOL-PRECISION-01` | Medium | `fluid-contracts/contracts/oracle/implementations/dex/dexSmartDebtOracleImpl.sol` | 21 | `: 1e18 / ((1e12 * TOKEN_1_DENOMINATOR_PRECISION) / TOKEN_1_NUMERATOR_PRECISION);` |
| `SOL-ORACLE-03` | High | `fluid-contracts/contracts/oracle/sourceReaders/chainlinkSourceReader.sol` | 8 | `try IChainlinkAggregatorV3(feed_).latestRoundData() returns (` |
| `SOL-ERC4626-06` | High | `fluid-contracts/contracts/periphery/resolvers/lending/main.sol` | 1 | `ERC4626 / convertToShares without _decimalsOffset or virtual shares` |
| `SOL-FOT-04` | Low/Medium | `fluid-contracts/contracts/periphery/wallet/factory/main.sol` | 130 | `VAULT_T1_FACTORY.safeTransferFrom(` |
| `SOL-FOT-04` | Low/Medium | `fluid-contracts/contracts/periphery/wethWrapper/main.sol` | 262 | `SafeTransfer.safeTransferFrom(address(asset), msg.sender, address(this), amount);` |
| `SOL-FOT-04` | Low/Medium | `fluid-contracts/contracts/periphery/wethWrapper/main.sol` | 352 | `SafeTransfer.safeTransferFrom(BORROW_TOKEN, onBehalfOf, address(this), uint256(amount));` |
| `SOL-FOT-04` | Low/Medium | `fluid-contracts/contracts/protocols/dex/poolT1/coreModule/core/main.sol` | 587 | `SafeTransfer.safeTransferFrom(token_, from_, address(LIQUIDITY), amountToSend_);` |
| `SOL-PRECISION-01` | Medium | `fluid-contracts/contracts/protocols/dex/poolT1/coreModule/core/main.sol` | 703 | `twap0by1_ += (1e54 / price_) * time_;` |
| `SOL-PRECISION-01` | Medium | `fluid-contracts/contracts/protocols/dex/poolT1/coreModule/core/main.sol` | 707 | `twap0by1_ += (1e54 / price_) * time_;` |
| `SOL-PRECISION-01` | Medium | `fluid-contracts/contracts/protocols/dex/poolT1/coreModule/core/main.sol` | 734 | `twap0by1_ = (1e54 / price_) * time_;` |
| `SOL-PRECISION-01` | Medium | `fluid-contracts/contracts/protocols/dex/poolT1/coreModule/core/main.sol` | 746 | `twap0by1_ = (1e54 / price_) * time_;` |
| `SOL-PRECISION-01` | Medium | `fluid-contracts/contracts/protocols/dex/poolT1/coreModule/helpers/coreHelpers.sol` | 670 | `p2_ = p2_ < 1e50 ? (p2_ * pb_) / 1e27 : (p2_ / 1e27) * pb_;` |
| `SOL-FOT-04` | Low/Medium | `fluid-contracts/contracts/protocols/dex/smartLending/main.sol` | 504 | `SafeTransfer.safeTransferFrom(token_, dexFromAddress, LIQUIDITY, amount_);` |
| `SOL-FOT-04` | Low/Medium | `fluid-contracts/contracts/protocols/dexLite/adminModule/helpers.sol` | 39 | `} else SafeTransfer.safeTransferFrom(token_, msg.sender, address(this), amount_);` |
| `SOL-FOT-04` | Low/Medium | `fluid-contracts/contracts/protocols/dexV2/base/core/adminModule.sol` | 138 | `SafeTransfer.safeTransferFrom(token_, msg.sender, address(this), uint256(amount_));` |
| `SOL-FOT-04` | Low/Medium | `fluid-contracts/contracts/protocols/dexV2/base/core/main.sol` | 262 | `else SafeTransfer.safeTransferFrom(token_, from_, address(LIQUIDITY), amountToSend_);` |
| `SOL-PRECISION-01` | Medium | `fluid-contracts/contracts/protocols/dexV2/dexTypes/d2/core/helpers.sol` | 120 | `p2_ = p2_ < 1e50 ? (p2_ * pb_) / 1e27 : (p2_ / 1e27) * pb_;` |
| `SOL-FOT-04` | Low/Medium | `fluid-contracts/contracts/protocols/lending/fToken/main.sol` | 979 | `SafeTransfer.safeTransferFrom(address(ASSET), from_, address(LIQUIDITY), amount_);` |
| `SOL-FOT-04` | Low/Medium | `fluid-contracts/contracts/protocols/lending/fToken/main.sol` | 988 | `PERMIT2.transferFrom(from_, address(LIQUIDITY), uint160(amount_), address(ASSET));` |
| `SOL-FOT-04` | Low/Medium | `fluid-contracts/contracts/protocols/lending/fToken/nativeUnderlying/fTokenNativeUnderlying.sol` | 118 | `PERMIT2.transferFrom(msg.sender, address(this), uint160(assets_), address(ASSET));` |
| `SOL-FOT-04` | Low/Medium | `fluid-contracts/contracts/protocols/lending/fToken/nativeUnderlying/fTokenNativeUnderlying.sol` | 120 | `SafeTransfer.safeTransferFrom(address(ASSET), msg.sender, address(this), assets_);` |
| `SOL-ERC4626-06` | High | `fluid-contracts/contracts/protocols/lending/fToken/nativeUnderlying/fTokenNativeUnderlying.sol` | 1 | `ERC4626 / convertToShares without _decimalsOffset or virtual shares` |
| `SOL-FOT-04` | Low/Medium | `fluid-contracts/contracts/protocols/lending/merkleDistributor/main.sol` | 316 | `if (pullFromDistributor) SafeERC20.safeTransferFrom(TOKEN, msg.sender, address(this), amount_);` |
| `SOL-FOT-04` | Low/Medium | `fluid-contracts/contracts/protocols/lending/stakingRewards/main.sol` | 166 | `stakingToken.safeTransferFrom(msg.sender, address(this), amount);` |
| `SOL-FOT-04` | Low/Medium | `fluid-contracts/contracts/protocols/lending/stakingRewards/main.sol` | 177 | `stakingToken.safeTransferFrom(msg.sender, address(this), amount);` |
| `SOL-FOT-04` | Low/Medium | `fluid-contracts/contracts/protocols/moneyMarket/core/base/main.sol` | 33 | `SafeTransfer.safeTransferFrom(token_, _msgSender, address(LIQUIDITY), amount_);` |
| `SOL-FOT-04` | Low/Medium | `fluid-contracts/contracts/protocols/moneyMarket/core/base/main.sol` | 49 | `SafeTransfer.safeTransferFrom(token_, _msgSender, to_, amount_);` |
| `SOL-FOT-04` | Low/Medium | `fluid-contracts/contracts/protocols/steth/main.sol` | 242 | `SafeERC20.safeTransferFrom(STETH, msg.sender, address(this), stETHAmount_);` |
| `SOL-FOT-04` | Low/Medium | `fluid-contracts/contracts/protocols/vault/vaultT1/coreModule/main.sol` | 1263 | `SafeTransfer.safeTransferFrom(token_, abi.decode(data_, (address)), address(LIQUIDITY), amount_);` |

_Showing top 40 of 42 deterministic pattern hits._

## Repository: `https://github.com/sherlock-audit/2025-07-oku-trade-order-types.git`
- Non-test/non-interface `.sol` files scanned: `15`
- Candidate pattern hits: `4`

| Rule ID | Severity | File | Line | Snippet |
|---|---|---|---:|---|
| `SOL-FOT-04` | Low/Medium | `oku-custom-order-types/contracts/automatedTrigger/Bracket.sol` | 408 | `token.safeTransferFrom(tokenOwner, address(this), amount);` |
| `SOL-FOT-04` | Low/Medium | `oku-custom-order-types/contracts/automatedTrigger/OracleLess.sol` | 406 | `token.safeTransferFrom(owner, address(this), amount);` |
| `SOL-FOT-04` | Low/Medium | `oku-custom-order-types/contracts/automatedTrigger/StopLimit.sol` | 239 | `tokenIn.safeTransferFrom(msg.sender, address(this), amountIn);` |
| `SOL-FOT-04` | Low/Medium | `oku-custom-order-types/contracts/automatedTrigger/StopLimit.sol` | 314 | `order.tokenIn.safeTransferFrom(` |

## Repository: `https://github.com/sherlock-audit/2025-07-cap.git`
- Non-test/non-interface `.sol` files scanned: `105`
- Candidate pattern hits: `12`

| Rule ID | Severity | File | Line | Snippet |
|---|---|---|---:|---|
| `SOL-AUTH-02` | High | `cap-contracts/contracts/deploy/utils/WalletUtils.sol` | 6 | `wallet = tx.origin;` |
| `SOL-FOT-04` | Low/Medium | `cap-contracts/contracts/feeAuction/FeeAuction.sol` | 67 | `IERC20($.paymentToken).safeTransferFrom(msg.sender, $.paymentRecipient, price);` |
| `SOL-FOT-04` | Low/Medium | `cap-contracts/contracts/lendingPool/libraries/BorrowLogic.sol` | 118 | `IERC20(params.asset).safeTransferFrom(params.caller, address(this), repaid);` |
| `SOL-PRECISION-01` | Medium | `cap-contracts/contracts/lendingPool/libraries/LiquidationLogic.sol` | 90 | `(liquidated + (liquidated * bonus / 1e27)) * assetPrice / (10 ** $.reservesData[params.asset].decimals);` |
| `SOL-PRECISION-01` | Medium | `cap-contracts/contracts/lendingPool/libraries/ViewLogic.sol` | 160 | `accruedInterest = totalDebt * rate * elapsedTime / (1e27 * SECONDS_IN_YEAR);` |
| `SOL-ORACLE-03` | High | `cap-contracts/contracts/oracle/libraries/ChainlinkAdapter.sol` | 17 | `(, intLatestAnswer,, lastUpdated,) = IChainlink(_source).latestRoundData();` |
| `SOL-PRECISION-01` | Medium | `cap-contracts/contracts/oracle/libraries/VaultAdapter.sol` | 95 | `interestRate = (slopes.slope0 + (slopes.slope1 * excess / 1e27)) * utilizationData.multiplier / 1e27;` |
| `SOL-PRECISION-01` | Medium | `cap-contracts/contracts/oracle/libraries/VaultAdapter.sol` | 104 | `interestRate = (slopes.slope0 * _utilization / slopes.kink) * utilizationData.multiplier / 1e27;` |
| `SOL-FOT-04` | Low/Medium | `cap-contracts/contracts/testnetCampaign/PreMainnetVault.sol` | 113 | `asset.safeTransferFrom(msg.sender, address(this), _amount);` |
| `SOL-ERC4626-06` | High | `cap-contracts/contracts/token/StakedCap.sol` | 1 | `ERC4626 / convertToShares without _decimalsOffset or virtual shares` |
| `SOL-FOT-04` | Low/Medium | `cap-contracts/contracts/vault/libraries/VaultLogic.sol` | 129 | `IERC20(params.asset).safeTransferFrom(msg.sender, address(this), params.amountIn);` |
| `SOL-FOT-04` | Low/Medium | `cap-contracts/contracts/vault/libraries/VaultLogic.sol` | 207 | `IERC20(params.asset).safeTransferFrom(msg.sender, address(this), params.amount);` |

## Repository: `https://github.com/sherlock-audit/2025-07-mellow-flexible-vaults.git`
- Non-test/non-interface `.sol` files scanned: `39`
- Candidate pattern hits: `2` (re-scanned after typed interface `.call()` filter refinement; removed 4 `ICallModule(subvault).call(...)` false positives)

| Rule ID | Severity | File | Line | Snippet |
|---|---|---|---:|---|
| `SOL-FOT-04` | Low/Medium | `flexible-vaults/src/libraries/TransferLibrary.sol` | 46 | `IERC20(asset).safeTransferFrom(from, address(this), assets);` |
| `SOL-ERC4626-06` | High | `flexible-vaults/src/managers/RiskManager.sol` | 1 | `ERC4626 / convertToShares without _decimalsOffset or virtual shares` |

## Repository: `https://github.com/sherlock-audit/2025-07-debank.git`
- Non-test/non-interface `.sol` files scanned: `49`
- Candidate pattern hits: `3`

| Rule ID | Severity | File | Line | Snippet |
|---|---|---|---:|---|
| `SOL-FOT-04` | Low/Medium | `swap-router-v1/src/aggregatorRouter/DexSwap.sol` | 138 | `IERC20(params.fromToken).safeTransferFrom(msg.sender, address(spender), params.fromTokenAmount);` |
| `SOL-FOT-04` | Low/Medium | `swap-router-v1/src/library/UniversalERC20.sol` | 30 | `token.safeTransferFrom(from, to, amount);` |
| `SOL-FOT-04` | Low/Medium | `swap-router-v1/src/router/Router.sol` | 77 | `IERC20(fromToken).safeTransferFrom(msg.sender, address(executor), fromTokenAmount);` |

## Repository: `https://github.com/sherlock-audit/2025-05-yearn-ybold.git`
- Non-test/non-interface `.sol` files scanned: `7`
- Candidate pattern hits: `2` (re-scanned after `SOL-ERC4626-06` non-vault `vault.totalAssets()` filter; removed `Accountant.sol` false positive)

| Rule ID | Severity | File | Line | Snippet |
|---|---|---|---:|---|
| `SOL-PRECISION-01` | Medium | `yv3-liquityv2-sp-strategy/src/Strategy.sol` | 241 | `AUCTION.setStartingPrice(_available * _price / WAD * _bufferPercentage / WAD / WAD);` |
| `SOL-PRECISION-01` | Medium | `yv3-liquityv2-sp-strategy/src/periphery/StrategyAprOracle.sol` | 115 | `return _weightedInterestRate / _totalDebt * _totalDebt / uint256(int256(_stabilityPoolDeposits) + _delta)` |

## Repository: `https://github.com/sherlock-audit/2025-06-symbiotic-relay.git`
- Non-test/non-interface `.sol` files scanned: `45`
- Candidate pattern hits: `3` (re-scanned after `/script/` deployment exclusion; removed `SymbioticInit.sol`)

| Rule ID | Severity | File | Line | Snippet |
|---|---|---|---:|---|
| `SOL-CALL-05` | Medium | `middleware-sdk/src/contracts/modules/voting-power/extensions/logic/BaseSlashingLogic.sol` | 88 | `(success, response) = slasher.call(` |
| `SOL-CALL-05` | Medium | `middleware-sdk/src/contracts/modules/voting-power/extensions/logic/BaseSlashingLogic.sol` | 96 | `(success, response) = slasher.call(` |
| `SOL-CALL-05` | Medium | `middleware-sdk/src/contracts/modules/voting-power/extensions/logic/BaseSlashingLogic.sol` | 129 | `(success, response) = slasher.call(abi.encodeCall(IVetoSlasher.executeSlash, (slashIndex, hints)));` |

## Repository: `https://github.com/sherlock-audit/2025-07-allbridge-core-yield.git`
- Non-test/non-interface `.sol` files scanned: `3`
- Candidate pattern hits: `0` (clean on static rules across `3` contracts; substituted after `code-423n4/2026-04-k2` & `2026-02-jupiter-lend` returned `0` `.sol` files)

## Repository: `https://github.com/hats-finance/Cross-chain-Realitio-Proxy-0x9efc47be23fb612aff9bce511bad4a308f1f4f39.git`
- Non-test/non-interface `.sol` files scanned: `14`
- Candidate pattern hits: `0`

## Repository: `https://github.com/hats-finance/dTRINITY-0xee5c6f15e8d0b55a5eff84bb66beeee0e6140ffe.git`
- Non-test/non-interface `.sol` files scanned: `219`
- Candidate pattern hits: `57` (top `15` representative findings below)

| Rule ID | Severity | File | Line | Snippet |
|---|---|---|---:|---|
| `SOL-ERC4626-06` | High | `bot/dlend-liquidator/contracts/aave-v3/FlashLoanLiquidatorAaveBorrowRepayBase.sol` | 1 | `ERC4626 / convertToShares without _decimalsOffset or virtual shares` |
| `SOL-ERC4626-06` | High | `contracts/common/RescuableVault.sol` | 1 | `ERC4626 / convertToShares without _decimalsOffset or virtual shares` |
| `SOL-ERC4626-06` | High | `contracts/common/SwappableVault.sol` | 1 | `ERC4626 / convertToShares without _decimalsOffset or virtual shares` |
| `SOL-INIT-08` | High | `contracts/dlend/core/dependencies/openzeppelin/upgradeability/InitializableUpgradeabilityProxy.sol` | 36 | `function initialize(address _logic, bytes memory _data) public payable {` |
| `SOL-ORACLE-03` | High | `contracts/dlend/core/protocol/configuration/PriceOracleSentinel.sol` | 101 | `.latestRoundData();` |
| `SOL-CALL-05` | Medium | `contracts/dlend/core/dependencies/openzeppelin/contracts/Address.sol` | 166 | `(bool success, bytes memory returndata) = target.call{value: value}(` |
| `SOL-FOT-04` | Low/Medium | `contracts/dlend/core/protocol/libraries/logic/BorrowLogic.sol` | 298 | `IERC20(params.asset).safeTransferFrom(` |
| `SOL-FOT-04` | Low/Medium | `contracts/dlend/core/protocol/libraries/logic/BridgeLogic.sol` | 178 | `IERC20(asset).safeTransferFrom(` |
| `SOL-FOT-04` | Low/Medium | `contracts/dlend/core/protocol/libraries/logic/FlashLoanLogic.sol` | 295 | `IERC20(params.asset).safeTransferFrom(` |
| `SOL-FOT-04` | Low/Medium | `contracts/dlend/core/protocol/libraries/logic/LiquidationLogic.sol` | 265 | `IERC20(params.debtAsset).safeTransferFrom(` |
| `SOL-FOT-04` | Low/Medium | `contracts/dlend/core/protocol/libraries/logic/SupplyLogic.sol` | 99 | `IERC20(params.asset).safeTransferFrom(` |
| `SOL-FOT-04` | Low/Medium | `contracts/dlend/periphery/adapters/curve/CurveDebtSwapAdapter.sol` | 274 | `IERC20WithPermit(aToken).safeTransferFrom(` |
| `SOL-FOT-04` | Low/Medium | `contracts/dlend/periphery/misc/WrappedTokenGatewayV3.sol` | 91 | `aWETH.transferFrom(msg.sender, address(this), amountToWithdraw);` |
| `SOL-FOT-04` | Low/Medium | `contracts/dstable/AmoManager.sol` | 176 | `dstable.transferFrom(amoVault, address(this), dstableAmount);` |
| `SOL-FOT-04` | Low/Medium | `contracts/dstable/CollateralHolderVault.sol` | 75 | `IERC20Metadata(fromCollateral).safeTransferFrom(` |
