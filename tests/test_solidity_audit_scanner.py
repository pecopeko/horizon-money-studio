"""Unit tests for deterministic Solidity static security scanner."""

from __future__ import annotations

from pathlib import Path

from makemoney.scouts.solidity_audit_scanner import (
    scan_solidity_source,
    scan_solidity_tree,
)


def test_detects_division_before_mul_oracle_and_erc4626_risks() -> None:
    vuln_sol = """
    // SPDX-License-Identifier: MIT
    pragma solidity ^0.8.20;
    contract VulnerableVault is ERC4626 {
        function getPrice(AggregatorV3Interface feed) external view returns (int256) {
            (, int256 price, , , ) = feed.latestRoundData();
            return price;
        }
        function calcFee(uint256 amt, uint256 rate) external pure returns (uint256) {
            return (amt / 10000) * rate;
        }
        function depositToken(IERC20 token, uint256 amt) external {
            token.transferFrom(msg.sender, address(this), amt);
        }
    }
    """
    findings = scan_solidity_source(vuln_sol, "src/VulnerableVault.sol")
    rule_ids = {f.rule_id for f in findings}
    assert "SOL-ORACLE-03" in rule_ids
    assert "SOL-PRECISION-01" in rule_ids
    assert "SOL-FOT-04" in rule_ids
    assert "SOL-ERC4626-06" in rule_ids


def test_ignores_comments_and_safe_oracle_vault_patterns(tmp_path: Path) -> None:
    safe_sol = """
    // (amt / 100) * fee  tx.origin inside comment must be ignored
    contract SafeVault is ERC4626 {
        function _decimalsOffset() internal pure override returns (uint8) { return 3; }
        function getPrice(AggregatorV3Interface feed) external view returns (uint256) {
            (, int256 answer, , uint256 updatedAt, ) = feed.latestRoundData();
            require(answer > 0 && block.timestamp - updatedAt <= 3600, "stale");
            return uint256(answer);
        }
    }
    """
    sol_file = tmp_path / "SafeVault.sol"
    sol_file.write_text(safe_sol, encoding="utf-8")
    test_file = tmp_path / "test" / "SafeVault.t.sol"
    test_file.parent.mkdir(parents=True)
    test_file.write_text("contract T { function f() external { require(tx.origin != address(0)); } }", encoding="utf-8")

    summary = scan_solidity_tree(tmp_path)
    assert summary["scanned_files"] == 1
    assert summary["findings_count"] == 0
