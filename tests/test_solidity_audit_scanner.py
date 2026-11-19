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


def test_ignores_interfaces_erc721_and_checked_tuple_calls(tmp_path: Path) -> None:
    iface_dir = tmp_path / "src" / "interfaces"
    iface_dir.mkdir(parents=True)
    (iface_dir / "IERC7575.sol").write_text(
        "interface IERC7575 { function convertToShares(uint256 assets) external view returns (uint256); }",
        encoding="utf-8",
    )
    (tmp_path / "src" / "IStandalone.sol").write_text(
        "interface IStandalone { function totalAssets() external view returns (uint256); }",
        encoding="utf-8",
    )
    safe_contracts = """
    pragma solidity ^0.8.20;
    contract SafeRouter {
        IERC721 public immutable loansNft;
        function transferLoan(address from, address to, uint256 id) external {
            loansNft.safeTransferFrom(from, to, id);
        }
        function safeForward(address target, bytes calldata data) external payable {
            bool ok;
            bytes memory ret;
            (ok, ret) = target.call{ value: msg.value }(data);
            if (!ok) revert();
        }
        function uncheckedForward(address target) external payable {
            bool ok;
            bytes memory ret;
            (ok, ret) = target.call{ value: msg.value }("");
        }
    }
    """
    (tmp_path / "src" / "SafeRouter.sol").write_text(safe_contracts, encoding="utf-8")

    iface_findings = scan_solidity_source(
        (tmp_path / "src" / "IStandalone.sol").read_text(encoding="utf-8"),
        "src/IStandalone.sol",
    )
    assert iface_findings == []

    summary = scan_solidity_tree(tmp_path)
    assert summary["scanned_files"] == 2
    rule_ids = [f["rule_id"] for f in summary["findings"]]
    assert "SOL-ERC4626-06" not in rule_ids
    assert "SOL-FOT-04" not in rule_ids
    assert rule_ids == ["SOL-CALL-05"]
    assert summary["findings"][0]["line_number"] == 17


def test_ignores_typed_interface_call_but_flags_raw_call() -> None:
    src = """
    pragma solidity ^0.8.20;
    contract CallSample {
        function ok(address subvault, bytes memory data) external {
            bytes memory approveResponse = ICallModule(subvault).call(data);
        }
        function bad(address target, bytes memory data) external {
            target.call(data);
        }
    }
    """
    findings = scan_solidity_source(src, "src/CallSample.sol")
    call_findings = [f for f in findings if f.rule_id == "SOL-CALL-05"]
    assert len(call_findings) == 1
    assert call_findings[0].line_number == 8


def test_ignores_external_total_assets_and_flags_zero_slippage() -> None:
    src = """
    pragma solidity ^0.8.20;
    contract AccountantHelper {
        function readVault(IVault vault) external returns (uint256) {
            uint256 tvl = vault.totalAssets();
            swapRouter.exactInputSingle(Params({ amountOutMinimum: 0 }));
            return tvl;
        }
    }
    """
    findings = scan_solidity_source(src, "src/AccountantHelper.sol")
    rule_ids = [f.rule_id for f in findings]
    assert "SOL-ERC4626-06" not in rule_ids
    assert rule_ids == ["SOL-SLIPPAGE-07"]
    assert findings[0].line_number == 6


def test_excludes_deployment_scripts_and_flags_unguarded_initialize(tmp_path: Path) -> None:
    src_dir = tmp_path / "src"
    script_dir = tmp_path / "script"
    src_dir.mkdir()
    script_dir.mkdir()

    (script_dir / "Deploy.s.sol").write_text(
        "contract DeployScript { function run() external { swap.call(\"\"); } }",
        encoding="utf-8",
    )
    (src_dir / "ProxyVault.sol").write_text(
        """
        pragma solidity ^0.8.20;
        contract BadInit {
            function initialize(address owner_) external {
                admin = owner_;
            }
        }
        contract GoodInit {
            function initialize(address owner_) external initializer {
                admin = owner_;
            }
        }
        """,
        encoding="utf-8",
    )

    summary = scan_solidity_tree(tmp_path)
    assert summary["scanned_files"] == 1
    init_findings = [f for f in summary["findings"] if f["rule_id"] == "SOL-INIT-08"]
    assert len(init_findings) == 1
    assert init_findings[0]["line_number"] == 4


def test_excludes_vendored_dependencies_and_flags_selfdestruct(tmp_path: Path) -> None:
    proto_dir = tmp_path / "contracts"
    deps_dir = tmp_path / "contracts" / "dependencies" / "openzeppelin"
    proto_dir.mkdir()
    deps_dir.mkdir(parents=True)

    (deps_dir / "Address.sol").write_text(
        "contract Address { function send() internal { target.call(\"\"); } }",
        encoding="utf-8",
    )
    (proto_dir / "LegacyPool.sol").write_text(
        """
        pragma solidity ^0.8.20;
        contract LegacyPool {
            function destroy(address payable to) external {
                selfdestruct(to);
            }
        }
        """,
        encoding="utf-8",
    )

    summary = scan_solidity_tree(tmp_path)
    assert summary["scanned_files"] == 1
    assert [f["rule_id"] for f in summary["findings"]] == ["SOL-SELFDESTRUCT-09"]
    assert summary["findings"][0]["line_number"] == 5




