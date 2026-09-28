# CLI examples

Common commands:

Replace the example destinations with addresses you control before running `instant-create`.

```bash
<skill-path>/scripts/liquidium-borrow max-borrow --collateral-asset BTC --borrow-asset USDC --collateral-amount-decimal 0.0005
<skill-path>/scripts/liquidium-borrow quote --collateral-asset BTC --borrow-asset USDC --collateral-amount-decimal 0.0005 --borrow-amount-decimal 9
<skill-path>/scripts/liquidium-borrow instant-create --collateral-asset BTC --borrow-asset USDC --collateral-amount-decimal 0.0005 --borrow-amount-decimal 9 --borrow-destination YOUR_EVM_ADDRESS --refund-destination YOUR_VALID_BTC_REFUND_ADDRESS
<skill-path>/scripts/liquidium-borrow loan-instructions --ref 8Y9AQQ --action status
<skill-path>/scripts/liquidium-borrow loan-instructions --ref 8Y9AQQ --action repay
<skill-path>/scripts/liquidium-borrow loan-instructions --ref 8Y9AQQ --action add-collateral
<skill-path>/scripts/liquidium-borrow deposit-status --ref 8Y9AQQ --txid <txid>
<skill-path>/scripts/liquidium-borrow instant-activities --ref 8Y9AQQ --filter active
<skill-path>/scripts/liquidium-borrow loan-list
<skill-path>/scripts/liquidium-borrow loan-show --ref 8Y9AQQ
<skill-path>/scripts/liquidium-borrow loan-tx --ref 8Y9AQQ --kind collateral --txid <txid>
<skill-path>/scripts/liquidium-borrow profile-summary --profile-id <profile-id>
```
