# Twin-2K-500 Replication — Detailed Analysis

## Framing Problem (framing)
- Citation: Tversky & Kahneman (1981)
- Paper result: replicated
- Our result: REPLICATED
- Stats: {
  "proportions_pct": {
    "gain": 0.6666666666666666,
    "loss": 59.333333333333336
  },
  "n_per_condition": {
    "gain": 150,
    "loss": 150
  },
  "chi2_stat": 120.14285714285714,
  "p_value": 5.886519935038323e-28,
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
    "single": 2.466666666666667,
    "conjunction": 4.706666666666667
  },
  "n_per_condition": {
    "single": 150,
    "conjunction": 150
  },
  "t_stat": -20.51624782415888,
  "p_value": 9.249186756987417e-57,
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
    "high_anchor": 357.17333333333335,
    "low_anchor": 354.93333333333334
  },
  "n_per_condition": {
    "high_anchor": 150,
    "low_anchor": 150
  },
  "t_stat": 0.1761741456059326,
  "p_value": 0.8603477692753024,
  "significant": false,
  "correct_direction": true,
  "replicated": false
}

## Anchoring & Adjustment (Mississippi River) (anchoring_mississippi)
- Citation: Tversky & Kahneman (1974)
- Paper result: not_replicated
- Our result: REPLICATED
- Stats: {
  "means": {
    "high_anchor": 2310.4666666666667,
    "low_anchor": 1807.16
  },
  "n_per_condition": {
    "high_anchor": 150,
    "low_anchor": 150
  },
  "t_stat": 8.015923948728336,
  "p_value": 3.381040307634476e-14,
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
    "cheap_item": 68.0,
    "expensive_item": 40.0
  },
  "n_per_condition": {
    "cheap_item": 150,
    "expensive_item": 150
  },
  "chi2_stat": 22.557702630166396,
  "p_value": 2.0392525172823217e-06,
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
    "domestic": 4.833333333333333
  },
  "n_per_condition": {
    "foreign": 150,
    "domestic": 150
  },
  "t_stat": 6.648873679428282,
  "p_value": 2.8286751906431577e-10,
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
    "overfilled": 3.6131333333333333,
    "underfilled": 3.7647333333333335
  },
  "n_per_condition": {
    "overfilled": 150,
    "underfilled": 150
  },
  "t_stat": -2.1999728149580813,
  "p_value": 0.028582640454626378,
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
    "wta_certain": 22.813333333333333,
    "wtp_certain": 26.943133333333332,
    "wtp_noncertain": 35.513333333333335
  },
  "n_per_condition": {
    "wta_certain": 150,
    "wtp_certain": 150,
    "wtp_noncertain": 150
  },
  "pairwise_tests": {
    "wta_certain_vs_wtp_certain": {
      "t": -7.047230022365588,
      "p": 1.2997490551041499e-11
    },
    "wtp_certain_vs_wtp_noncertain": {
      "t": -20.77333016882412,
      "p": 4.727918728363408e-50
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
    "paid": 30.666666666666668,
    "free": 0.0
  },
  "n_per_condition": {
    "paid": 150,
    "free": 150
  },
  "chi2_stat": 51.99418007531668,
  "p_value": 5.566538026285687e-13,
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
    "good_outcome": 5.873333333333333,
    "bad_outcome": 4.506666666666667
  },
  "n_per_condition": {
    "good_outcome": 150,
    "bad_outcome": 150
  },
  "t_stat": 15.310369186745545,
  "p_value": 1.8375978292874229e-38,
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
  "problem2_pct_risky_B": 68.0,
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
    "low_baserate": 45.20666666666666,
    "high_baserate": 77.96666666666667
  },
  "n_per_condition": {
    "low_baserate": 150,
    "high_baserate": 150
  },
  "t_stat": -16.12416676116331,
  "p_value": 5.401518147938206e-41,
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
  "pearson_r": 0.5729813283696098,
  "p_value": 1.196074670412612e-53,
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
      "r": 0.08458370004530222,
      "p": 0.30342611279994036,
      "replicated": "False"
    },
    "pesticides": {
      "r": -0.19930802232757805,
      "p": 0.014478038534609262,
      "replicated": "True"
    },
    "alcohol": {
      "r": -0.27041312074368123,
      "p": 0.0008176778005730825,
      "replicated": "True"
    },
    "cars": {
      "r": 0.13055094706309311,
      "p": 0.11130314988994011,
      "replicated": "False"
    },
    "cigarettes": {
      "r": -0.39117305985508943,
      "p": 7.441828082100131e-07,
      "replicated": "True"
    },
    "xrays": {
      "r": -0.14102261340271918,
      "p": 0.08519062496031857,
      "replicated": "False"
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
  "commission_pct_skip": 5.333333333333333,
  "omission_pct_skip": 65.33333333333333,
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
  "pct_dominated": 0.0,
  "correct_direction": false,
  "replicated": false
}
