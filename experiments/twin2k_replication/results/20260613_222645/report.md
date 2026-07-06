# Twin-2K-500 Replication — Detailed Analysis

## Framing Problem (framing)
- Citation: Tversky & Kahneman (1981)
- Paper result: replicated
- Our result: REPLICATED
- Stats: {
  "proportions_pct": {
    "gain": 0.0,
    "loss": 87.33333333333333
  },
  "n_per_condition": {
    "gain": 150,
    "loss": 150
  },
  "chi2_stat": 229.00763358778627,
  "p_value": 9.812126583045702e-52,
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
    "single": 2.46,
    "conjunction": 4.34
  },
  "n_per_condition": {
    "single": 150,
    "conjunction": 150
  },
  "t_stat": -19.927709690603436,
  "p_value": 2.3730795969144693e-55,
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
    "high_anchor": 708.96,
    "low_anchor": 225.06
  },
  "n_per_condition": {
    "high_anchor": 150,
    "low_anchor": 150
  },
  "t_stat": 13.673594440082908,
  "p_value": 8.190603274115416e-29,
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
    "high_anchor": 2842.4666666666667,
    "low_anchor": 1742.9333333333334
  },
  "n_per_condition": {
    "high_anchor": 150,
    "low_anchor": 150
  },
  "t_stat": 10.126597111641962,
  "p_value": 7.991419227599601e-21,
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
    "cheap_item": 28.0,
    "expensive_item": 2.6666666666666665
  },
  "n_per_condition": {
    "cheap_item": 150,
    "expensive_item": 150
  },
  "chi2_stat": 35.150633344744946,
  "p_value": 3.0516214358267833e-09,
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
    "foreign": 5.253333333333333,
    "domestic": 4.766666666666667
  },
  "n_per_condition": {
    "foreign": 150,
    "domestic": 150
  },
  "t_stat": 3.373241229886653,
  "p_value": 0.0008444844616986509,
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
    "overfilled": 4.986666666666666,
    "underfilled": 5.013333333333334
  },
  "n_per_condition": {
    "overfilled": 150,
    "underfilled": 150
  },
  "t_stat": -0.3104100146136136,
  "p_value": 0.7564662923203743,
  "significant": false,
  "correct_direction": false,
  "replicated": false
}

## WTA/WTP (Endowment Effect) (wta_wtp)
- Citation: Thaler (1980); Stanovich & West (2008)
- Paper result: replicated
- Our result: NOT REPLICATED
- Stats: {
  "means": {
    "wta_certain": 29.92,
    "wtp_certain": 29.053333333333335,
    "wtp_noncertain": 32.16
  },
  "n_per_condition": {
    "wta_certain": 150,
    "wtp_certain": 150,
    "wtp_noncertain": 150
  },
  "pairwise_tests": {
    "wta_certain_vs_wtp_certain": {
      "t": 3.9487621933128234,
      "p": 0.00011628235100521278
    },
    "wtp_certain_vs_wtp_noncertain": {
      "t": -8.03910319141622,
      "p": 3.224793875515775e-14
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
    "paid": 67.33333333333333,
    "free": 0.6666666666666666
  },
  "n_per_condition": {
    "paid": 150,
    "free": 150
  },
  "chi2_stat": 145.58823529411765,
  "p_value": 1.5972020058245725e-33,
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
    "good_outcome": 5.28,
    "bad_outcome": 4.233333333333333
  },
  "n_per_condition": {
    "good_outcome": 150,
    "bad_outcome": 150
  },
  "t_stat": 10.249457133344887,
  "p_value": 4.927158338327543e-21,
  "significant": true,
  "correct_direction": true,
  "replicated": true
}

## Allais Problem (allais)
- Citation: Allais (1953); Stanovich & West (2008)
- Paper result: not_replicated
- Our result: REPLICATED
- Stats: {
  "problem1_pct_safe_A": 98.66666666666667,
  "problem2_pct_risky_B": 74.66666666666667,
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
    "low_baserate": 75.5,
    "high_baserate": 80.0
  },
  "n_per_condition": {
    "low_baserate": 150,
    "high_baserate": 150
  },
  "t_stat": -2.759440349239219,
  "p_value": 0.006190214387636095,
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
  "pearson_r": 0.2838399138074861,
  "p_value": 1.3970367139070376e-12,
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
      "r": -0.27089995611868833,
      "p": 0.0007994041155333295,
      "replicated": "True"
    },
    "pesticides": {
      "r": -0.19081922042391303,
      "p": 0.019333724312410372,
      "replicated": "True"
    },
    "alcohol": {
      "r": -0.3350407614039811,
      "p": 2.7791789983124427e-05,
      "replicated": "True"
    },
    "cars": {
      "r": 0.47360029798210745,
      "p": 9.302914646856061e-10,
      "replicated": "False"
    },
    "cigarettes": {
      "r": -0.7994830825013118,
      "p": 1.4182638461905772e-34,
      "replicated": "True"
    },
    "xrays": {
      "r": -0.695983259928413,
      "p": 4.809028785259675e-23,
      "replicated": "True"
    }
  },
  "replicated_count": 5,
  "total_items": 6,
  "replicated": true,
  "summary": "5/6 items show negative risk-benefit correlation"
}

## Omission Bias (omission_bias)
- Citation: Spranca, Minsk & Baron (1991)
- Paper result: not_replicated
- Our result: NOT REPLICATED
- Stats: {
  "commission_pct_skip": 20.666666666666668,
  "omission_pct_skip": 87.33333333333333,
  "n_per_condition": {
    "commission": 150,
    "omission": 150
  },
  "correct_direction": false,
  "replicated": false
}

## Probability Matching vs. Maximizing (probability_matching)
- Citation: Vulkan (2000); Stanovich & West (2008)
- Paper result: not_replicated
- Our result: REPLICATED
- Stats: {
  "n": 150,
  "pct_matching": 30.0,
  "pct_maximizing": 70.0,
  "human_benchmark_pct_matching": 30.0,
  "correct_direction": true,
  "replicated": true
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
