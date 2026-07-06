# Twin-2K-500 Replication — Detailed Analysis

## Framing Problem (framing)
- Citation: Tversky & Kahneman (1981)
- Paper result: replicated
- Our result: REPLICATED
- Stats: {
  "proportions_pct": {
    "gain": 0.0,
    "loss": 83.33333333333333
  },
  "n_per_condition": {
    "gain": 150,
    "loss": 150
  },
  "chi2_stat": 210.87085714285712,
  "p_value": 8.868931287430192e-48,
  "significant": true,
  "correct_direction": true,
  "replicated": true
}

## Conjunction Problem (Linda) (linda)
- Citation: Tversky & Kahneman (1983)
- Paper result: replicated
- Our result: REPLICATED
- Stats: {
  "means": {
    "single": 2.3066666666666666,
    "conjunction": 3.98
  },
  "n_per_condition": {
    "single": 150,
    "conjunction": 150
  },
  "t_stat": -32.61440791121975,
  "p_value": 3.113265069219298e-99,
  "significant": true,
  "correct_direction": true,
  "replicated": true
}

## Anchoring & Adjustment (Redwood Tree) (anchoring_redwood)
- Citation: Tversky & Kahneman (1974)
- Paper result: replicated
- Our result: REPLICATED
- Stats: {
  "means": {
    "high_anchor": 379.82666666666665,
    "low_anchor": 305.14666666666665
  },
  "n_per_condition": {
    "high_anchor": 150,
    "low_anchor": 150
  },
  "t_stat": 5.08552883824381,
  "p_value": 9.698367895033033e-07,
  "significant": true,
  "correct_direction": true,
  "replicated": true
}

## Anchoring & Adjustment (Mississippi River) (anchoring_mississippi)
- Citation: Tversky & Kahneman (1974)
- Paper result: not_replicated
- Our result: REPLICATED
- Stats: {
  "means": {
    "high_anchor": 2724.0466666666666,
    "low_anchor": 2101.0733333333333
  },
  "n_per_condition": {
    "high_anchor": 150,
    "low_anchor": 150
  },
  "t_stat": 7.708307033927335,
  "p_value": 2.1304818504684562e-13,
  "significant": true,
  "correct_direction": true,
  "replicated": true
}

## Absolute vs. Relative Savings (savings)
- Citation: Tversky & Kahneman (1981)
- Paper result: replicated
- Our result: NOT REPLICATED
- Stats: {
  "proportions_pct": {
    "cheap_item": 0.6666666666666666,
    "expensive_item": 0.6666666666666666
  },
  "n_per_condition": {
    "cheap_item": 150,
    "expensive_item": 150
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
- Our result: REPLICATED
- Stats: {
  "means": {
    "foreign": 5.806666666666667,
    "domestic": 5.066666666666666
  },
  "n_per_condition": {
    "foreign": 150,
    "domestic": 150
  },
  "t_stat": 7.071797822590587,
  "p_value": 1.9485715871735126e-11,
  "significant": true,
  "correct_direction": true,
  "replicated": true
}

## Less is More (less_is_more)
- Citation: Hsee (1998)
- Paper result: replicated
- Our result: NOT REPLICATED
- Stats: {
  "means": {
    "overfilled": 3.8132,
    "underfilled": 3.7932
  },
  "n_per_condition": {
    "overfilled": 150,
    "underfilled": 150
  },
  "t_stat": 0.282235545118274,
  "p_value": 0.7779633883296204,
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
    "wta_certain": 31.266666666666666,
    "wtp_certain": 25.06,
    "wtp_noncertain": 30.673333333333332
  },
  "n_per_condition": {
    "wta_certain": 150,
    "wtp_certain": 150,
    "wtp_noncertain": 150
  },
  "pairwise_tests": {
    "wta_certain_vs_wtp_certain": {
      "t": 24.800773454651853,
      "p": 2.506257394335683e-56
    },
    "wtp_certain_vs_wtp_noncertain": {
      "t": -35.99800788314193,
      "p": 3.211596453681707e-82
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
    "free": 0.0
  },
  "n_per_condition": {
    "paid": 150,
    "free": 150
  },
  "chi2_stat": NaN,
  "p_value": 1.0,
  "significant": false,
  "correct_direction": false,
  "replicated": false
}

## Outcome Bias (outcome_bias)
- Citation: Baron & Hershey (1988)
- Paper result: not_replicated
- Our result: REPLICATED
- Stats: {
  "means": {
    "good_outcome": 6.586666666666667,
    "bad_outcome": 2.72
  },
  "n_per_condition": {
    "good_outcome": 150,
    "bad_outcome": 150
  },
  "t_stat": 43.7458436807459,
  "p_value": 1.7300130731965778e-131,
  "significant": true,
  "correct_direction": true,
  "replicated": true
}

## Allais Problem (allais)
- Citation: Allais (1953); Stanovich & West (2008)
- Paper result: not_replicated
- Our result: REPLICATED
- Stats: {
  "problem1_pct_safe_A": 100.0,
  "problem2_pct_risky_B": 96.66666666666667,
  "n_per_condition": {
    "problem1": 150,
    "problem2": 150
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
    "low_baserate": 78.96666666666667,
    "high_baserate": 79.36666666666666
  },
  "n_per_condition": {
    "low_baserate": 150,
    "high_baserate": 150
  },
  "t_stat": -0.42845774184967833,
  "p_value": 0.6686335813612623,
  "significant": false,
  "correct_direction": true,
  "replicated": false
}

## False Consensus Effect (false_consensus)
- Citation: Ross, Greene & House (1977)
- Paper result: replicated
- Our result: REPLICATED
- Stats: {
  "n_pairs": 600,
  "pearson_r": 0.6203085782615134,
  "p_value": 4.356892747036203e-65,
  "correct_direction": "True",
  "replicated": "True"
}

## Risk-Benefit Nonseparability (risk_benefit)
- Citation: Alhakami & Slovic (1994)
- Paper result: partial
- Our result: REPLICATED
- Stats: {
  "items": {
    "nuclear": {
      "r": -0.15946225186768653,
      "p": 0.05127643889641252,
      "replicated": "False"
    },
    "pesticides": {
      "r": -0.39305532348997974,
      "p": 6.511647606558096e-07,
      "replicated": "True"
    },
    "alcohol": {
      "r": -0.3730412216856354,
      "p": 2.58352189440436e-06,
      "replicated": "True"
    },
    "cars": {
      "r": 0.3375539087973274,
      "p": 2.3973417212397906e-05,
      "replicated": "False"
    },
    "cigarettes": {
      "r": -0.23537304069773546,
      "p": 0.003738137699833366,
      "replicated": "True"
    },
    "xrays": {
      "r": -0.47621307761082476,
      "p": 7.30089559250055e-10,
      "replicated": "True"
    }
  },
  "replicated_count": 4,
  "total_items": 6,
  "replicated": true,
  "summary": "4/6 items show negative risk-benefit correlation"
}

## Omission Bias (omission_bias)
- Citation: Spranca, Minsk & Baron (1991)
- Paper result: not_replicated
- Our result: REPLICATED
- Stats: {
  "commission_pct_skip": 18.0,
  "omission_pct_skip": 15.333333333333334,
  "n_per_condition": {
    "commission": 150,
    "omission": 150
  },
  "correct_direction": true,
  "replicated": true
}

## Probability Matching vs. Maximizing (probability_matching)
- Citation: Vulkan (2000); Stanovich & West (2008)
- Paper result: not_replicated
- Our result: NOT REPLICATED
- Stats: {
  "n": 150,
  "pct_matching": 0.0,
  "pct_maximizing": 100.0,
  "human_benchmark_pct_matching": 30.0,
  "correct_direction": false,
  "replicated": false
}

## Dominator Neglect (dominator_neglect)
- Citation: Bar-Hillel & Neter (1993); Stanovich & West (2008)
- Paper result: replicated
- Our result: NOT REPLICATED
- Stats: {
  "n": 150,
  "pct_dominated": 0.0,
  "correct_direction": false,
  "replicated": false
}
