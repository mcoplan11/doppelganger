# Twin-2K-500 Replication — Detailed Analysis

## Default Effect — Green Energy (defaults_green)
- Citation: Peng et al. 2025 Mega-Study (Defaults); orig. Pichert & Katsikopoulos (2008)
- Paper result: replicated
- Our result: REPLICATED
- Stats: {
  "proportions_pct": {
    "optin": 0.6666666666666666,
    "optout": 29.333333333333332
  },
  "n_per_condition": {
    "optin": 150,
    "optout": 150
  },
  "chi2_stat": 46.117647058823536,
  "p_value": 1.1136085483338326e-11,
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
    "optin": 34.666666666666664,
    "optout": 98.0
  },
  "n_per_condition": {
    "optin": 150,
    "optout": 150
  },
  "chi2_stat": 131.88715856510274,
  "p_value": 1.5837020706875716e-30,
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
    "targeted": 5.66,
    "broad": 5.766666666666667
  },
  "n_per_condition": {
    "targeted": 150,
    "broad": 150
  },
  "t_stat": -0.5036475674767533,
  "p_value": 0.6149103447244887,
  "significant": false,
  "correct_direction": true,
  "replicated": false
}
