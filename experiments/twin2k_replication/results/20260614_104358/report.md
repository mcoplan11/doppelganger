# Twin-2K-500 Replication — Detailed Analysis

## Framing Problem (framing)
- Citation: Tversky & Kahneman (1981)
- Paper result: replicated
- Our result: REPLICATED
- Stats: {
  "proportions_pct": {
    "gain": 0.0,
    "loss": 35.333333333333336
  },
  "n_per_condition": {
    "gain": 150,
    "loss": 150
  },
  "chi2_stat": 61.96623634558093,
  "p_value": 3.493970203436033e-15,
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
    "single": 2.6333333333333333,
    "conjunction": 5.0
  },
  "n_per_condition": {
    "single": 150,
    "conjunction": 150
  },
  "t_stat": -37.12386902487599,
  "p_value": 1.8719696143278602e-113,
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
    "high_anchor": 533.4866666666667,
    "low_anchor": 293.0
  },
  "n_per_condition": {
    "high_anchor": 150,
    "low_anchor": 150
  },
  "t_stat": 9.061030917524592,
  "p_value": 3.634079994559362e-16,
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
    "high_anchor": 2973.86,
    "low_anchor": 2137.173333333333
  },
  "n_per_condition": {
    "high_anchor": 150,
    "low_anchor": 150
  },
  "t_stat": 9.788006815592386,
  "p_value": 2.0059191227642608e-19,
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
    "cheap_item": 84.0,
    "expensive_item": 72.0
  },
  "n_per_condition": {
    "cheap_item": 150,
    "expensive_item": 150
  },
  "chi2_stat": 5.613830613830614,
  "p_value": 0.017819267806478124,
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
    "foreign": 5.86,
    "domestic": 5.226666666666667
  },
  "n_per_condition": {
    "foreign": 150,
    "domestic": 150
  },
  "t_stat": 5.7372630500706405,
  "p_value": 3.097301751189426e-08,
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
    "overfilled": 4.505,
    "underfilled": 4.473333333333334
  },
  "n_per_condition": {
    "overfilled": 150,
    "underfilled": 150
  },
  "t_stat": 0.3556368071386381,
  "p_value": 0.7223652281985942,
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
    "wta_certain": 28.173333333333332,
    "wtp_certain": 26.206533333333333,
    "wtp_noncertain": 34.26
  },
  "n_per_condition": {
    "wta_certain": 150,
    "wtp_certain": 150,
    "wtp_noncertain": 150
  },
  "pairwise_tests": {
    "wta_certain_vs_wtp_certain": {
      "t": 3.466213772443951,
      "p": 0.0006190398461035257
    },
    "wtp_certain_vs_wtp_noncertain": {
      "t": -14.219463076309257,
      "p": 3.287816017040504e-34
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
    "paid": 22.0,
    "free": 0.0
  },
  "n_per_condition": {
    "paid": 150,
    "free": 150
  },
  "chi2_stat": 34.8655090228124,
  "p_value": 3.532841567280084e-09,
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
    "good_outcome": 6.1066666666666665,
    "bad_outcome": 3.486666666666667
  },
  "n_per_condition": {
    "good_outcome": 150,
    "bad_outcome": 150
  },
  "t_stat": 28.284824955939012,
  "p_value": 2.1877438992455384e-86,
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
  "problem2_pct_risky_B": 96.0,
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
    "low_baserate": 49.89333333333333,
    "high_baserate": 67.54666666666667
  },
  "n_per_condition": {
    "low_baserate": 150,
    "high_baserate": 150
  },
  "t_stat": -11.68691001742494,
  "p_value": 1.291818739480587e-25,
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
  "pearson_r": 0.373884944597067,
  "p_value": 2.415867455988361e-21,
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
      "r": -0.5051018318693574,
      "p": 4.3517407052322274e-11,
      "replicated": "True"
    },
    "pesticides": {
      "r": -0.25723529228511,
      "p": 0.001484117262089643,
      "replicated": "True"
    },
    "alcohol": {
      "r": -0.36930819509440266,
      "p": 3.307627073619735e-06,
      "replicated": "True"
    },
    "cars": {
      "r": 0.08938961190636716,
      "p": 0.27667654435083405,
      "replicated": "False"
    },
    "cigarettes": {
      "r": -0.3711526877639411,
      "p": 2.9286288345698427e-06,
      "replicated": "True"
    },
    "xrays": {
      "r": -0.04114428112425972,
      "p": 0.6171393058449204,
      "replicated": "False"
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
  "commission_pct_skip": 9.333333333333334,
  "omission_pct_skip": 99.33333333333333,
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
  "pct_dominated": 0.6666666666666666,
  "correct_direction": false,
  "replicated": false
}
