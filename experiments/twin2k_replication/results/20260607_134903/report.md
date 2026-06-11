# Twin-2K-500 Replication — Detailed Analysis

## Framing Problem (framing)
- Citation: Tversky & Kahneman (1981)
- Paper result: replicated
- Our result: NOT REPLICATED
- Stats: {
  "proportions_pct": {
    "gain": 0.0,
    "loss": 66.66666666666667
  },
  "n_per_condition": {
    "gain": 3,
    "loss": 3
  },
  "chi2_stat": 0.75,
  "p_value": 0.3864762307712325,
  "significant": false,
  "correct_direction": true,
  "replicated": false
}

## Conjunction Problem (Linda) (linda)
- Citation: Tversky & Kahneman (1983)
- Paper result: replicated
- Our result: NOT REPLICATED
- Stats: {
  "means": {
    "single": 2.3333333333333335,
    "conjunction": 2.0
  },
  "n_per_condition": {
    "single": 3,
    "conjunction": 3
  },
  "t_stat": 0.5000000000000002,
  "p_value": 0.6494501780131947,
  "significant": false,
  "correct_direction": false,
  "replicated": false
}

## Anchoring & Adjustment (Redwood Tree) (anchoring_redwood)
- Citation: Tversky & Kahneman (1974)
- Paper result: replicated
- Our result: NOT REPLICATED
- Stats: {
  "means": {
    "high_anchor": 716.6666666666666,
    "low_anchor": 350.0
  },
  "n_per_condition": {
    "high_anchor": 3,
    "low_anchor": 3
  },
  "t_stat": 1.2435135216772872,
  "p_value": 0.3396697522935694,
  "significant": false,
  "correct_direction": true,
  "replicated": false
}

## Anchoring & Adjustment (Mississippi River) (anchoring_mississippi)
- Citation: Tversky & Kahneman (1974)
- Paper result: not_replicated
- Our result: NOT REPLICATED
- Stats: {
  "means": {
    "high_anchor": 2733.3333333333335,
    "low_anchor": 1966.6666666666667
  },
  "n_per_condition": {
    "high_anchor": 3,
    "low_anchor": 3
  },
  "t_stat": 2.2885855374829753,
  "p_value": 0.08404636344767656,
  "significant": false,
  "correct_direction": true,
  "replicated": false
}

## Absolute vs. Relative Savings (savings)
- Citation: Tversky & Kahneman (1981)
- Paper result: replicated
- Our result: NOT REPLICATED
- Stats: {
  "proportions_pct": {
    "cheap_item": 0.0,
    "expensive_item": 33.333333333333336
  },
  "n_per_condition": {
    "cheap_item": 2,
    "expensive_item": 3
  },
  "chi2_stat": 0.0,
  "p_value": 1.0,
  "significant": false,
  "correct_direction": false,
  "replicated": false
}

## Myside Bias (myside)
- Citation: Stanovich & West (2008)
- Paper result: replicated
- Our result: NOT REPLICATED
- Stats: {
  "means": {
    "foreign": 5.0,
    "domestic": 5.0
  },
  "n_per_condition": {
    "foreign": 3,
    "domestic": 3
  },
  "t_stat": 0.0,
  "p_value": 1.0,
  "significant": false,
  "correct_direction": false,
  "replicated": false
}

## Less is More (less_is_more)
- Citation: Hsee (1998)
- Paper result: replicated
- Our result: NOT REPLICATED
- Stats: {
  "means": {
    "overfilled": 5.666666666666667,
    "underfilled": 5.0
  },
  "n_per_condition": {
    "overfilled": 3,
    "underfilled": 3
  },
  "t_stat": 0.852802865422442,
  "p_value": 0.44330487975017924,
  "significant": false,
  "correct_direction": true,
  "replicated": false
}

## WTA/WTP (Endowment Effect) (wta_wtp)
- Citation: Thaler (1980); Stanovich & West (2008)
- Paper result: replicated
- Our result: NOT REPLICATED
- Stats: {
  "means": {
    "wta_certain": 30.666666666666668,
    "wtp_certain": 28.326666666666664,
    "wtp_noncertain": 35.333333333333336
  },
  "n_per_condition": {
    "wta_certain": 3,
    "wtp_certain": 3,
    "wtp_noncertain": 3
  },
  "pairwise_tests": {
    "wta_certain_vs_wtp_certain": {
      "t": 1.3058323980929438,
      "p": 0.29421518530277035
    },
    "wtp_certain_vs_wtp_noncertain": {
      "t": -4.130303746340065,
      "p": 0.04718636179853121
    }
  },
  "correct_direction": false,
  "replicated": false
}

## Sunk Cost Fallacy (sunk_cost)
- Citation: Arkes & Blumer (1985)
- Paper result: not_replicated
- Our result: NOT REPLICATED
- Stats: {
  "proportions_pct": {
    "paid": 0.0,
    "free": 33.333333333333336
  },
  "n_per_condition": {
    "paid": 3,
    "free": 3
  },
  "chi2_stat": 0.0,
  "p_value": 1.0,
  "significant": false,
  "correct_direction": false,
  "replicated": false
}

## Outcome Bias (outcome_bias)
- Citation: Baron & Hershey (1988)
- Paper result: not_replicated
- Our result: NOT REPLICATED
- Stats: {
  "means": {
    "good_outcome": 6.333333333333333,
    "bad_outcome": 5.0
  },
  "n_per_condition": {
    "good_outcome": 3,
    "bad_outcome": 3
  },
  "t_stat": 1.5118578920369086,
  "p_value": 0.2065258321579969,
  "significant": false,
  "correct_direction": true,
  "replicated": false
}

## Allais Problem (allais)
- Citation: Allais (1953); Stanovich & West (2008)
- Paper result: not_replicated
- Our result: REPLICATED
- Stats: {
  "problem1_pct_safe_A": 66.66666666666667,
  "problem2_pct_risky_B": 100.0,
  "n_per_condition": {
    "problem1": 3,
    "problem2": 3
  },
  "correct_direction": true,
  "replicated": true
}

## Base Rate Problem (base_rate)
- Citation: Kahneman & Tversky (1973)
- Paper result: not_replicated
- Our result: NOT REPLICATED
- Stats: {
  "means": {
    "low_baserate": 81.66666666666667,
    "high_baserate": 81.66666666666667
  },
  "n_per_condition": {
    "low_baserate": 3,
    "high_baserate": 3
  },
  "t_stat": 0.0,
  "p_value": 1.0,
  "significant": false,
  "correct_direction": false,
  "replicated": false
}

## False Consensus Effect (false_consensus)
- Citation: Ross, Greene & House (1977)
- Paper result: replicated
- Our result: NOT REPLICATED
- Stats: {
  "n_pairs": 12,
  "pearson_r": 0.4361898423992996,
  "p_value": 0.1563145398249522,
  "correct_direction": "True",
  "replicated": "False"
}

## Risk-Benefit Nonseparability (risk_benefit)
- Citation: Alhakami & Slovic (1994)
- Paper result: partial
- Our result: NOT REPLICATED
- Stats: {
  "items": {
    "nuclear": {
      "r": NaN,
      "p": NaN,
      "replicated": "False"
    },
    "pesticides": {
      "r": 0.11470786693528096,
      "p": 0.9268136049596726,
      "replicated": "False"
    },
    "cars": {
      "r": 0.9999999999999998,
      "p": 1.3415758552508148e-08,
      "replicated": "False"
    },
    "cigarettes": {
      "r": NaN,
      "p": NaN,
      "replicated": "False"
    },
    "xrays": {
      "r": 0.49999999999999994,
      "p": 0.6666666666666666,
      "replicated": "False"
    }
  },
  "replicated_count": 0,
  "total_items": 5,
  "replicated": false,
  "summary": "0/5 items show negative risk-benefit correlation"
}

## Omission Bias (omission_bias)
- Citation: Spranca, Minsk & Baron (1991)
- Paper result: not_replicated
- Our result: NOT REPLICATED
- Stats: {
  "proportions_pct": {
    "commission": 0.0,
    "omission": 0.0
  },
  "n_per_condition": {
    "commission": 3,
    "omission": 3
  },
  "chi2_stat": NaN,
  "p_value": NaN,
  "significant": false,
  "correct_direction": false,
  "replicated": false
}

## Probability Matching vs. Maximizing (probability_matching)
- Citation: Vulkan (2000); Stanovich & West (2008)
- Paper result: not_replicated
- Our result: REPLICATED
- Stats: {
  "n": 3,
  "pct_matching": 33.333333333333336,
  "pct_maximizing": 66.66666666666667,
  "human_benchmark_pct_matching": 30.0,
  "correct_direction": true,
  "replicated": true
}

## Dominator Neglect (dominator_neglect)
- Citation: Bar-Hillel & Neter (1993); Stanovich & West (2008)
- Paper result: replicated
- Our result: NOT REPLICATED
- Stats: {
  "n": 3,
  "pct_dominated": 0.0,
  "correct_direction": false,
  "replicated": false
}
