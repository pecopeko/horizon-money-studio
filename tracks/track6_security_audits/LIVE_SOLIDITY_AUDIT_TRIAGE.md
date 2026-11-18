# Live Solidity Audit Competition & Safe-Harbor Scan Triage

Deterministic static vulnerability pre-screen produced by `src/makemoney/scouts/solidity_audit_scanner.py` (candidates require manual economic/PoC validation before reporting).

## Repository: `https://github.com/sherlock-audit/2026-07-tare.git`
- Non-test `.sol` files scanned: `41`
- Candidate pattern hits: `10`

| Rule ID | Severity | File | Line | Snippet |
|---|---|---|---:|---|
| `SOL-FOT-04` | Low/Medium | `tare-io__tare-contracts/contracts/LoansExchange.sol` | 120 | `LOANS_NFT.transferFrom(seller, msg.sender, uint256(loanIds[i]));` |
| `SOL-FOT-04` | Low/Medium | `tare-io__tare-contracts/contracts/LoansExchange.sol` | 125 | `CURRENCY.safeTransferFrom(msg.sender, seller, uint256(price));` |
| `SOL-FOT-04` | Low/Medium | `tare-io__tare-contracts/contracts/LoansLedger.sol` | 252 | `currency.safeTransferFrom(addr, address(this), uint256(int256(amount)));` |
| `SOL-FOT-04` | Low/Medium | `tare-io__tare-contracts/contracts/PortfolioVault.sol` | 583 | `IERC721(address(loansNFT)).transferFrom(address(this), recipient, uint256(loanId));` |
| `SOL-FOT-04` | Low/Medium | `tare-io__tare-contracts/contracts/PortfolioVault.sol` | 612 | `assetToken.safeTransferFrom(owner, address(this), assets);` |
| `SOL-FOT-04` | Low/Medium | `tare-io__tare-contracts/contracts/PortfolioVault.sol` | 738 | `IERC20(address(shareToken)).safeTransferFrom(owner, address(this), shares);` |
| `SOL-FOT-04` | Low/Medium | `tare-io__tare-contracts/contracts/TrustedSpender.sol` | 98 | `IERC20(token).safeTransferFrom(from, to, amount);` |
| `SOL-FOT-04` | Low/Medium | `tare-io__tare-contracts/contracts/TrustedSpender.sol` | 139 | `IERC721(collection).transferFrom(from, to, tokenId);` |
| `SOL-FOT-04` | Low/Medium | `tare-io__tare-contracts/contracts/misc/Rescuable.sol` | 45 | `IERC721(token).safeTransferFrom(address(this), recoveryAddress, tokenId);` |
| `SOL-ERC4626-06` | High | `tare-io__tare-contracts/contracts/misc/interfaces/IERC7575.sol` | 1 | `ERC4626 / convertToShares without _decimalsOffset or virtual shares` |

## Repository: `https://github.com/Cyfrin/battlechain-safe-harbor-contracts.git`
- Non-test `.sol` files scanned: `29`
- Candidate pattern hits: `6`

| Rule ID | Severity | File | Line | Snippet |
|---|---|---|---:|---|
| `SOL-FOT-04` | Low/Medium | `src/BondManager.sol` | 211 | `s_bondToken.safeTransferFrom(payer, s_treasury, fee);` |
| `SOL-FOT-04` | Low/Medium | `src/BondManager.sol` | 214 | `s_bondToken.safeTransferFrom(payer, address(this), bondAmount);` |
| `SOL-CALL-05` | Medium | `src/CreateX.sol` | 183 | `(success, returnData) = refundAddress.call{ value: _SELF.balance }("");` |
| `SOL-CALL-05` | Medium | `src/CreateX.sol` | 424 | `(success, returnData) = refundAddress.call{ value: _SELF.balance }("");` |
| `SOL-CALL-05` | Medium | `src/CreateX.sol` | 760 | `(success, returnData) = newContract.call{ value: values.initCallAmount }(data);` |
| `SOL-CALL-05` | Medium | `src/CreateX.sol` | 768 | `(success, returnData) = refundAddress.call{ value: _SELF.balance }("");` |

## Repository: `https://github.com/code-423n4/2026-04-monetrix.git`
- Non-test `.sol` files scanned: `21`
- Candidate pattern hits: `5`

| Rule ID | Severity | File | Line | Snippet |
|---|---|---|---:|---|
| `SOL-FOT-04` | Low/Medium | `src/core/InsuranceFund.sol` | 40 | `usdc.safeTransferFrom(msg.sender, address(this), amount);` |
| `SOL-FOT-04` | Low/Medium | `src/core/MonetrixVault.sol` | 178 | `usdc.safeTransferFrom(msg.sender, address(this), amount);` |
| `SOL-FOT-04` | Low/Medium | `src/core/MonetrixVault.sol` | 185 | `IERC20(address(usdm)).safeTransferFrom(msg.sender, address(this), usdmAmount);` |
| `SOL-FOT-04` | Low/Medium | `src/tokens/sUSDM.sol` | 240 | `IERC20(asset()).safeTransferFrom(msg.sender, address(this), usdmAmount);` |
| `SOL-FOT-04` | Low/Medium | `src/tokens/sUSDMEscrow.sol` | 34 | `usdm.safeTransferFrom(sUSDM, address(this), amount);` |
