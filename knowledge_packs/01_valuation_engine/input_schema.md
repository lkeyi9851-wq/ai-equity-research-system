# Valuation Input Schema

Required fields when available:

```text
ticker
market
currency
price
price_date
price_source
shares_outstanding
market_cap
net_debt_or_net_cash
enterprise_value
revenue_actual
revenue_forecast
EBIT_actual
EBIT_forecast
net_income_actual
EPS_actual
EPS_forecast
OCF_actual
FCF_actual
FCF_forecast
FCF_per_share
P_E
P_FCF
EV_EBITDA
peer_median_multiple
historical_multiple_range
target_price_external
target_price_source
source_type
freshness_label: live / recent / stale / analyst-report-only
data_label: actual / estimate / assumption
```

Minimum publishable valuation:
- price
- price date
- one earnings or cash-flow metric
- one formula-derived multiple
- source label for every input

If any minimum field is absent, show a data gap instead of a valuation case.
