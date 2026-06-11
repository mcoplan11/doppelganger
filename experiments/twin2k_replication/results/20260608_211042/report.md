# Twin-2K-500 Replication — Detailed Analysis

## Framing Problem (framing)
- Citation: Tversky & Kahneman (1981)
- Paper result: replicated
- Our result: REPLICATED
- Stats: {
  "proportions_pct": {
    "gain": 0.6666666666666666,
    "loss": 62.0
  },
  "n_per_condition": {
    "gain": 150,
    "loss": 150
  },
  "chi2_stat": 128.29477380706467,
  "p_value": 9.675153134633064e-30,
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
    "single": 2.4466666666666668,
    "conjunction": 4.713333333333333
  },
  "n_per_condition": {
    "single": 150,
    "conjunction": 150
  },
  "t_stat": -20.04637430707631,
  "p_value": 5.961268526538589e-56,
  "significant": true,
  "correct_direction": true,
  "replicated": true
}

## Anchoring & Adjustment (Redwood Tree) (anchoring_redwood)
- Citation: Tversky & Kahneman (1974)
- Paper result: replicated
- Our result: NOT REPLICATED
- Stats: {
  "means": {
    "high_anchor": 349.8933333333333,
    "low_anchor": 350.96
  },
  "n_per_condition": {
    "high_anchor": 150,
    "low_anchor": 150
  },
  "t_stat": -0.08186030937857075,
  "p_value": 0.9348394230683822,
  "significant": false,
  "correct_direction": false,
  "replicated": false
}

## Anchoring & Adjustment (Mississippi River) (anchoring_mississippi)
- Citation: Tversky & Kahneman (1974)
- Paper result: not_replicated
- Our result: REPLICATED
- Stats: {
  "means": {
    "high_anchor": 2265.846666666667,
    "low_anchor": 1754.8533333333332
  },
  "n_per_condition": {
    "high_anchor": 150,
    "low_anchor": 150
  },
  "t_stat": 7.2614315424307545,
  "p_value": 3.411774553130223e-12,
  "significant": true,
  "correct_direction": true,
  "replicated": true
}

## Absolute vs. Relative Savings (savings)
- Citation: Tversky & Kahneman (1981)
- Paper result: replicated
- Our result: REPLICATED
- Stats: {
  "proportions_pct": {
    "cheap_item": 71.33333333333333,
    "expensive_item": 41.333333333333336
  },
  "n_per_condition": {
    "cheap_item": 150,
    "expensive_item": 150
  },
  "chi2_stat": 26.23424725597362,
  "p_value": 3.024115863266376e-07,
  "significant": true,
  "correct_direction": true,
  "replicated": true
}

## Myside Bias (myside)
- Citation: Stanovich & West (2008)
- Paper result: replicated
- Our result: REPLICATED
- Stats: {
  "means": {
    "foreign": 5.806666666666667,
    "domestic": 4.82
  },
  "n_per_condition": {
    "foreign": 150,
    "domestic": 150
  },
  "t_stat": 6.258268022124447,
  "p_value": 2.1611536843977036e-09,
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
    "overfilled": 3.6364666666666667,
    "underfilled": 3.8232
  },
  "n_per_condition": {
    "overfilled": 150,
    "underfilled": 150
  },
  "t_stat": -2.300609215814375,
  "p_value": 0.022166282817780655,
  "significant": true,
  "correct_direction": false,
  "replicated": false
}

## WTA/WTP (Endowment Effect) (wta_wtp)
- Citation: Thaler (1980); Stanovich & West (2008)
- Paper result: replicated
- Our result: NOT REPLICATED
- Stats: {
  "means": {
    "wta_certain": 22.9,
    "wtp_certain": 26.87993333333333,
    "wtp_noncertain": 35.64
  },
  "n_per_condition": {
    "wta_certain": 150,
    "wtp_certain": 150,
    "wtp_noncertain": 150
  },
  "pairwise_tests": {
    "wta_certain_vs_wtp_certain": {
      "t": -7.003705130233304,
      "p": 1.9096679328223583e-11
    },
    "wtp_certain_vs_wtp_noncertain": {
      "t": -24.401946502399124,
      "p": 1.521766857307033e-59
    }
  },
  "correct_direction": false,
  "replicated": false
}

## Sunk Cost Fallacy (sunk_cost)
- Citation: Arkes & Blumer (1985)
- Paper result: not_replicated
- Our result: REPLICATED
- Stats: {
  "proportions_pct": {
    "paid": 38.0,
    "free": 0.0
  },
  "n_per_condition": {
    "paid": 150,
    "free": 150
  },
  "chi2_stat": 67.92289365388781,
  "p_value": 1.7001565709503608e-16,
  "significant": true,
  "correct_direction": true,
  "replicated": true
}

## Outcome Bias (outcome_bias)
- Citation: Baron & Hershey (1988)
- Paper result: not_replicated
- Our result: REPLICATED
- Stats: {
  "means": {
    "good_outcome": 5.92,
    "bad_outcome": 4.513333333333334
  },
  "n_per_condition": {
    "good_outcome": 150,
    "bad_outcome": 150
  },
  "t_stat": 16.10463134627882,
  "p_value": 7.63140392358098e-41,
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
  "problem2_pct_risky_B": 64.0,
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
- Our result: REPLICATED
- Stats: {
  "means": {
    "low_baserate": 45.74,
    "high_baserate": 76.93333333333334
  },
  "n_per_condition": {
    "low_baserate": 150,
    "high_baserate": 150
  },
  "t_stat": -15.763453789811368,
  "p_value": 1.1182429662411651e-39,
  "significant": true,
  "correct_direction": true,
  "replicated": true
}

## False Consensus Effect (false_consensus)
- Citation: Ross, Greene & House (1977)
- Paper result: replicated
- Our result: REPLICATED
- Stats: {
  "n_pairs": 600,
  "pearson_r": 0.5537617142113879,
  "p_value": 1.6326217890347497e-49,
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
      "r": -0.0787041916104041,
      "p": 0.3383916884381162,
      "replicated": "False"
    },
    "pesticides": {
      "r": -0.017255580925993906,
      "p": 0.8339919660074405,
      "replicated": "False"
    },
    "alcohol": {
      "r": -0.4939192949868173,
      "p": 1.3376270160315708e-10,
      "replicated": "True"
    },
    "cars": {
      "r": 0.16859838623345771,
      "p": 0.039168323303120825,
      "replicated": "False"
    },
    "cigarettes": {
      "r": -0.42549912122251465,
      "p": 5.7016583825405076e-08,
      "replicated": "True"
    },
    "xrays": {
      "r": -0.2221364179545127,
      "p": 0.006293854391849746,
      "replicated": "True"
    }
  },
  "replicated_count": 3,
  "total_items": 6,
  "replicated": true,
  "summary": "3/6 items show negative risk-benefit correlation"
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
    "commission": 150,
    "omission": 150
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
