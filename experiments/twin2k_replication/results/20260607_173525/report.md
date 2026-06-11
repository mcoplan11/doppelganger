# Twin-2K-500 Replication — Detailed Analysis

## Framing Problem (framing)
- Citation: Tversky & Kahneman (1981)
- Paper result: replicated
- Our result: REPLICATED
- Stats: {
  "proportions_pct": {
    "gain": 0.0,
    "loss": 31.333333333333332
  },
  "n_per_condition": {
    "gain": 150,
    "loss": 150
  },
  "chi2_stat": 53.38491295938104,
  "p_value": 2.7419459041043846e-13,
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
    "single": 2.473333333333333,
    "conjunction": 3.92
  },
  "n_per_condition": {
    "single": 150,
    "conjunction": 150
  },
  "t_stat": -12.04445828996934,
  "p_value": 5.404162809902234e-27,
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
    "high_anchor": 604.0666666666667,
    "low_anchor": 280.3333333333333
  },
  "n_per_condition": {
    "high_anchor": 150,
    "low_anchor": 150
  },
  "t_stat": 10.456662893184886,
  "p_value": 5.455298994341919e-20,
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
    "high_anchor": 3414.0,
    "low_anchor": 1549.6
  },
  "n_per_condition": {
    "high_anchor": 150,
    "low_anchor": 150
  },
  "t_stat": 15.544029511097714,
  "p_value": 2.434310074479595e-37,
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
    "cheap_item": 3.3333333333333335,
    "expensive_item": 1.3333333333333333
  },
  "n_per_condition": {
    "cheap_item": 150,
    "expensive_item": 150
  },
  "chi2_stat": 0.5850804485616772,
  "p_value": 0.4443278090087417,
  "significant": false,
  "correct_direction": true,
  "replicated": false
}

## Myside Bias (myside)
- Citation: Stanovich & West (2008)
- Paper result: replicated
- Our result: REPLICATED
- Stats: {
  "means": {
    "foreign": 5.26,
    "domestic": 4.326666666666667
  },
  "n_per_condition": {
    "foreign": 150,
    "domestic": 150
  },
  "t_stat": 5.7549432819969235,
  "p_value": 2.191104738607276e-08,
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
    "overfilled": 4.453333333333333,
    "underfilled": 4.526666666666666
  },
  "n_per_condition": {
    "overfilled": 150,
    "underfilled": 150
  },
  "t_stat": -0.6562755239274569,
  "p_value": 0.5121566351767789,
  "significant": false,
  "correct_direction": false,
  "replicated": false
}

## WTA/WTP (Endowment Effect) (wta_wtp)
- Citation: Thaler (1980); Stanovich & West (2008)
- Paper result: replicated
- Our result: REPLICATED
- Stats: {
  "means": {
    "wta_certain": 29.44,
    "wtp_certain": 24.639666666666667,
    "wtp_noncertain": 20.44
  },
  "n_per_condition": {
    "wta_certain": 150,
    "wtp_certain": 150,
    "wtp_noncertain": 150
  },
  "pairwise_tests": {
    "wta_certain_vs_wtp_certain": {
      "t": 10.314384430595496,
      "p": 3.675739133916178e-20
    },
    "wtp_certain_vs_wtp_noncertain": {
      "t": 5.35683020880734,
      "p": 1.8715896096270493e-07
    }
  },
  "correct_direction": true,
  "replicated": true
}

## Sunk Cost Fallacy (sunk_cost)
- Citation: Arkes & Blumer (1985)
- Paper result: not_replicated
- Our result: REPLICATED
- Stats: {
  "proportions_pct": {
    "paid": 74.0,
    "free": 6.0
  },
  "n_per_condition": {
    "paid": 150,
    "free": 150
  },
  "chi2_stat": 141.68055555555557,
  "p_value": 1.1421685230667164e-32,
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
    "bad_outcome": 3.7333333333333334
  },
  "n_per_condition": {
    "good_outcome": 150,
    "bad_outcome": 150
  },
  "t_stat": 12.402586513194652,
  "p_value": 9.581667032580854e-29,
  "significant": true,
  "correct_direction": true,
  "replicated": true
}

## Allais Problem (allais)
- Citation: Allais (1953); Stanovich & West (2008)
- Paper result: not_replicated
- Our result: REPLICATED
- Stats: {
  "problem1_pct_safe_A": 98.0,
  "problem2_pct_risky_B": 98.0,
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
    "low_baserate": 79.6,
    "high_baserate": 85.4
  },
  "n_per_condition": {
    "low_baserate": 150,
    "high_baserate": 150
  },
  "t_stat": -3.4088501043202073,
  "p_value": 0.0007552249139742092,
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
  "pearson_r": 0.31857505326891566,
  "p_value": 1.2804134952776749e-15,
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
      "r": -0.16015523684695215,
      "p": 0.050260480593757234,
      "replicated": "False"
    },
    "pesticides": {
      "r": -0.34041325975626985,
      "p": 2.0231244455653294e-05,
      "replicated": "True"
    },
    "alcohol": {
      "r": -0.3230316182907756,
      "p": 5.5339164722219006e-05,
      "replicated": "True"
    },
    "cars": {
      "r": 0.30099080654391885,
      "p": 0.00018205086758362648,
      "replicated": "False"
    },
    "cigarettes": {
      "r": -0.5806457293454933,
      "p": 6.782665325333897e-15,
      "replicated": "True"
    },
    "xrays": {
      "r": -0.4759076018663863,
      "p": 7.511496542020473e-10,
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
- Our result: REPLICATED
- Stats: {
  "n": 150,
  "pct_matching": 20.0,
  "pct_maximizing": 80.0,
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
