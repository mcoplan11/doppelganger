# Twin-2K-500 Replication — Detailed Analysis

## Default Effect — Green Energy (defaults_green)
- Citation: Peng et al. 2025 Mega-Study (Defaults); orig. Pichert & Katsikopoulos (2008)
- Paper result: replicated
- Our result: REPLICATED
- Stats: {
  "proportions_pct": {
    "optin": 1.3333333333333333,
    "optout": 87.33333333333333
  },
  "n_per_condition": {
    "optin": 150,
    "optout": 150
  },
  "chi2_stat": 221.29575435594973,
  "p_value": 4.717916089753643e-50,
  "significant": true,
  "correct_direction": true,
  "replicated": true
}

## Default Effect — Organ Donation (defaults_organ)
- Citation: Peng et al. 2025 Mega-Study (Defaults); orig. Johnson & Goldstein (2003)
- Paper result: null_in_humans
- Our result: REPLICATED
- Stats: {
  "proportions_pct": {
    "optin": 2.0,
    "optout": 100.0
  },
  "n_per_condition": {
    "optin": 150,
    "optout": 150
  },
  "chi2_stat": 284.3270641589969,
  "p_value": 8.564050257980328e-64,
  "significant": true,
  "correct_direction": true,
  "replicated": true
}

## Targeting Fairness (Gender-Based Advertising) (targeting_fairness)
- Citation: Peng et al. 2025 Mega-Study (Targeting fairness)
- Paper result: replicated
- Our result: NOT REPLICATED
- Stats: {
  "means": {
    "targeted": 5.8133333333333335,
    "broad": 6.006666666666667
  },
  "n_per_condition": {
    "targeted": 150,
    "broad": 150
  },
  "t_stat": -1.6013718154740515,
  "p_value": 0.11040549704994371,
  "significant": false,
  "correct_direction": true,
  "replicated": false
}
