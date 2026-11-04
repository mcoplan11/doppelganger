// Data for the /biases pages: one entry per classic heuristics-and-biases
// experiment from our Twin-2K-500 replication benchmark (see /research).
// Each page pairs the textbook treatment of a bias with our own data on
// whether AI respondents reproduce it — the part no other site can write.
// Statistics come from the final reconciled benchmark run (ensemble 15.5/17).

export type BiasStatus = "yes" | "partial" | "no";

export type Bias = {
  slug: string;
  name: string;
  /** Short query-shaped page heading, e.g. "What is the anchoring effect?" */
  title: string;
  description: string; // meta description
  status: BiasStatus;
  definition: string;
  classicStudy: string; // design + citation + original finding
  example: string; // concrete everyday / survey example
  aiResult: string; // our benchmark result with numbers
  surveyTip: string; // what it means for questionnaire design / pretesting
  related: string[]; // slugs
};

export const BIASES: Bias[] = [
  {
    slug: "framing-effect",
    name: "Framing effect",
    title: "What is the framing effect?",
    description:
      "The framing effect: Tversky & Kahneman's Asian disease problem, a concrete example, and benchmark data on whether AI survey respondents show the bias.",
    status: "yes",
    definition:
      "The framing effect is the tendency for people to reach different decisions depending on whether logically equivalent options are described in terms of gains or losses. Risk preferences flip with the wording: people tend to play it safe when outcomes are framed as gains and take risks when the same outcomes are framed as losses.",
    classicStudy:
      "In Tversky and Kahneman's (1981) 'Asian disease problem,' participants chose between two programs to combat a disease expected to kill 600 people. In the gain frame, a sure option 'saves 200 lives' competes with a gamble; in the loss frame, the same sure option is described as '400 people will die.' Although the options are numerically identical, the sure option dominated in the gain frame while the gamble dominated in the loss frame.",
    example:
      "A medical consent form that says a procedure has a '90% survival rate' produces more uptake than one that says it has a '10% mortality rate' — same number, different frame. In surveys, an attitude item about a policy that 'creates jobs for 95% of workers' will not score the same as one about a policy that 'leaves 5% unemployed.'",
    aiResult:
      "Reproduced, strongly. In our benchmark (N = 147 AI respondents per condition), 0% chose the risky option under the gain frame versus 55.8% under the loss frame — χ² = 110.96, p < .001, and every model in the ensemble showed the flip. If anything, AI respondents frame-shift more sharply than humans do.",
    surveyTip:
      "If your study involves any numerical outcome — prices, risks, success rates — the frame is part of your manipulation whether you intended it or not. Pretest both framings: if your effect only exists under one wording, you want to know that before you field.",
    related: ["anchoring-effect", "allais-paradox", "relative-savings"],
  },
  {
    slug: "conjunction-fallacy",
    name: "Conjunction fallacy",
    title: "What is the conjunction fallacy? The Linda problem",
    description:
      "The conjunction fallacy and the famous Linda problem: why people rate a conjunction as more probable than its parts, and whether AI respondents make the same mistake.",
    status: "yes",
    definition:
      "The conjunction fallacy is judging a conjunction of two events as more probable than one of its components alone — a logical impossibility, since 'A and B' can never be more likely than just 'A.' It happens because a richer, more representative story feels more plausible even as it becomes mathematically less probable.",
    classicStudy:
      "Tversky and Kahneman (1983) described Linda — 31, single, outspoken, a philosophy major concerned with social justice — and asked how likely she is to be 'a bank teller' versus 'a bank teller who is active in the feminist movement.' Most participants rated the conjunction as more likely than the single event, because the added detail fits the sketch, even though it strictly shrinks the probability.",
    example:
      "Consumer researchers hit this constantly: 'How likely are you to buy this product?' and 'How likely are you to buy this product when it goes on sale?' can produce inverted probability judgments, because the added condition makes the scenario more vivid.",
    aiResult:
      "Reproduced, with a huge effect. Our AI respondents rated the conjunction (M = 4.73 on a 1–6 likelihood scale) far above the single event (M = 2.62) in a within-subjects design — paired t = 26.5, p < .001, N = 150 — and all models in the ensemble showed it. The 'too rational to be fooled' worry does not hold here.",
    surveyTip:
      "Watch for unintended conjunctions in your own items. A question that stacks conditions ('useful and easy to use,' 'would buy if recommended by a friend') invites representativeness-driven answers rather than probability judgments. Pretesting surfaces items where added detail is doing the work.",
    related: ["base-rate-neglect", "false-consensus-effect", "framing-effect"],
  },
  {
    slug: "anchoring-effect",
    name: "Anchoring effect",
    title: "What is the anchoring effect?",
    description:
      "The anchoring effect: Tversky & Kahneman's classic estimation experiments, examples in pricing and surveys, and benchmark data on whether AI respondents anchor too.",
    status: "yes",
    definition:
      "Anchoring is the tendency for numerical judgments to be pulled toward a previously presented number — even an arbitrary or obviously uninformative one. The anchor sets a starting point, and adjustment away from it is usually insufficient, so final estimates land closer to the anchor than they should.",
    classicStudy:
      "In the paradigm introduced by Tversky and Kahneman (1974), people first judge whether a quantity is above or below an anchor, then estimate it. Asked whether the tallest redwood is taller or shorter than 1,200 feet, people estimate far higher than those asked about a 180-foot anchor. The same works for the length of the Mississippi River with 5,000-mile versus 500-mile anchors.",
    example:
      "A 'suggested donation: $50' field raises average gifts relative to a $5 suggestion. In surveys, a prior question mentioning any number — an income bracket, a reference price, last year's figure — can anchor every numeric estimate that follows it.",
    aiResult:
      "Reproduced on both tasks, in every model. High-anchor AI respondents estimated the tallest redwood at 563 feet on average versus 293 feet in the low-anchor condition (t = 11.2, p < .001), and the Mississippi at 2,958 versus 1,863 miles (t = 13.2, p < .001), N = 150 per condition. Anchoring is one of the most robust effects in our entire benchmark.",
    surveyTip:
      "Question order is a manipulation. If your survey collects numeric estimates, audit every number a respondent sees first — scale endpoints, example values, previous questions. An AI pretest with the order randomized is a cheap way to detect whether an accidental anchor is driving your DV.",
    related: ["framing-effect", "relative-savings", "base-rate-neglect"],
  },
  {
    slug: "relative-savings",
    name: "Absolute vs. relative savings",
    title: "The jacket–calculator problem: why we drive across town to save $5",
    description:
      "Tversky & Kahneman's absolute vs. relative savings problem: why a $5 discount feels different on a $15 item than a $125 one, with AI replication data.",
    status: "yes",
    definition:
      "People evaluate savings relative to the price of the item rather than in absolute dollars. The same $5 is worth a 20-minute drive when it's a third off a cheap item, but not when it's 4% off an expensive one — even though the money and the drive are identical.",
    classicStudy:
      "Tversky and Kahneman (1981) asked participants whether they would drive 20 minutes to save $5 on a $15 calculator; most said yes. Asked the same question about a $125 calculator, most said no. A rational shopper should make the same choice in both cases — the question is whether 20 minutes is worth $5.",
    example:
      "Shoppers who clip coupons on groceries will ignore a $200 difference between car dealerships. In pricing research, discount framing (percent off versus dollars off) changes willingness to buy in ways that pure economics says it shouldn't.",
    aiResult:
      "Reproduced. 38.7% of AI respondents would make the drive to save $5 on the cheap item versus 14.0% on the expensive one (χ² = 22.3, p < .001, N = 150 per condition). Four of the five models in our ensemble showed the effect individually.",
    surveyTip:
      "If your study involves prices or incentives, the reference magnitude is a hidden factor. Pretest your scenarios at more than one price point — an effect that only appears against small reference prices is a scoping discovery you want to make for a few dollars, not after fielding.",
    related: ["anchoring-effect", "endowment-effect", "framing-effect"],
  },
  {
    slug: "myside-bias",
    name: "Myside bias",
    title: "What is myside bias?",
    description:
      "Myside bias: evaluating arguments and policies more favorably when they benefit your own group, with the Stanovich & West auto-safety experiment and AI replication data.",
    status: "yes",
    definition:
      "Myside bias is the tendency to evaluate evidence, arguments, and policies more favorably when they align with one's own group, identity, or prior position. Unlike many biases, it is largely unrelated to intelligence — smart people show it just as strongly.",
    classicStudy:
      "Stanovich and West (2008) asked Americans whether a country should be allowed to sell cars that fail the other country's safety standards. When the unsafe car was German and sold in the US, people objected strongly; when it was American and sold in Germany, the identical arrangement drew much weaker objections.",
    example:
      "Respondents rate the same policy proposal as fairer when it's attributed to their own party, and the same essay as better written when they agree with its conclusion. Any survey touching politics, nationality, or group membership is exposed.",
    aiResult:
      "Reproduced. AI respondents disapproved more strongly when the manufacturer was foreign (M = 5.24 on a 1–6 scale) than when it was domestic (M = 4.68) — t = 3.96, p < .001, N = 150 per condition. Four of five models showed the asymmetry. Persona-conditioned AI respondents inherit group-serving evaluation, not just demographic labels.",
    surveyTip:
      "If your vignettes name groups, countries, or brands, those identities are part of the stimulus. Counterbalance them, and check in a pretest whether your effect survives when the group labels flip — if it doesn't, you've measured myside bias, not your construct.",
    related: ["false-consensus-effect", "outcome-bias", "omission-bias"],
  },
  {
    slug: "less-is-more-effect",
    name: "Less-is-more effect",
    title: "The less-is-more effect: when people pay more for less",
    description:
      "Hsee's ice-cream experiment: why an overfilled small cup beats an underfilled large one, and what happened when AI respondents faced the same choice.",
    status: "yes",
    definition:
      "In separate evaluation, people judge options by how easy they are to evaluate rather than by objective quantity — so a smaller amount that looks generous can be valued above a larger amount that looks stingy. The quantity cue people can read (fullness) beats the one that matters (ounces).",
    classicStudy:
      "Hsee (1998) showed participants either 7 oz of ice cream heaped over the brim of a 5-oz cup or 8 oz sitting at 80% of a 10-oz cup, and asked what they'd pay. The overfilled smaller serving earned higher willingness to pay than the objectively larger one.",
    example:
      "A 24-piece dinnerware set in perfect condition sells for more than a 31-piece set that includes a few broken items — the extra intact pieces add value, but the broken ones poison the evaluation. Package sizing and portion framing in consumer research live on this effect.",
    aiResult:
      "Reproduced by the ensemble, but only barely at the model level: just one of the five models showed it (overfilled M = $4.71 vs. underfilled M = $4.46, t = 5.05, p < .001, N ≈ 150 per condition). Most individual models correctly valued the larger quantity — a concrete case of AI respondents being too rational, and a good illustration of why we run an ensemble rather than one model.",
    surveyTip:
      "Effects that depend on evaluability are exactly where an AI pretest deserves the most caution — a null in a single model means little here. If your manipulation hinges on what's easy versus hard to evaluate, treat the AI result as a smoke test and lean on human pilots sooner.",
    related: ["endowment-effect", "dominance-neglect", "relative-savings"],
  },
  {
    slug: "sunk-cost-fallacy",
    name: "Sunk-cost fallacy",
    title: "What is the sunk-cost fallacy?",
    description:
      "The sunk-cost fallacy: Arkes & Blumer's ski-trip experiment, real-world examples, and whether AI survey respondents honor sunk costs too.",
    status: "yes",
    definition:
      "The sunk-cost fallacy is letting unrecoverable past costs influence present decisions. Money already spent shouldn't change which option is better now — but having paid makes people stick with the inferior choice to avoid 'wasting' it.",
    classicStudy:
      "Arkes and Blumer (1985) had participants imagine holding tickets to two ski trips on the same weekend: a $100 trip to Michigan and a $50 trip to Wisconsin they expected to enjoy more. More people chose the less-enjoyable Michigan trip when they had paid for it than when the ticket was free.",
    example:
      "Finishing a boring movie because you paid for the ticket; continuing a failing project because of what it has already cost; respondents in longitudinal studies rating a product they purchased more favorably than an identical one they received free.",
    aiResult:
      "Reproduced. 15.5% of AI respondents chose the inferior trip when they had paid $100 for it, versus 2.1% when it was free (χ² = 14.95, p < .001, N ≈ 147 per condition). Four of the five models showed the effect. The absolute rates are lower than typical human samples, but the paid-versus-free gap is unmistakable.",
    surveyTip:
      "Scenario studies involving prior investment should vary the sunk amount explicitly — it's a powerful lever respondents react to even when it's logically irrelevant. A pretest tells you whether your scenario's sunk cost is driving behavior you meant to attribute to something else.",
    related: ["endowment-effect", "outcome-bias", "allais-paradox"],
  },
  {
    slug: "outcome-bias",
    name: "Outcome bias",
    title: "What is outcome bias?",
    description:
      "Outcome bias: Baron & Hershey's surgery experiment — judging the same decision differently by how it turned out — with AI respondent replication data.",
    status: "yes",
    definition:
      "Outcome bias is judging the quality of a decision by its outcome rather than by what was knowable when the decision was made. A sensible gamble that failed gets rated as a bad decision; a reckless one that succeeded gets rated as good.",
    classicStudy:
      "Baron and Hershey (1988) described a surgeon deciding to operate on a heart patient, with identical information in both conditions. When told the patient survived, participants rated the decision as significantly better than when told the patient died — though the decision itself was the same.",
    example:
      "Performance reviews that punish well-reasoned bets that didn't pay off; consumers rating identical purchase decisions differently depending on whether the product later went on sale; respondents evaluating a manager's identical choice by its random outcome.",
    aiResult:
      "Reproduced, with one of the largest effects in our benchmark. AI respondents rated the identical decision at M = 5.85 (1–7 scale) after a good outcome versus M = 3.93 after a bad one — t = 19.4, p < .001, N ≈ 150 per condition, every model in the ensemble.",
    surveyTip:
      "If your vignette reveals an outcome, it will contaminate every judgment that follows. Either hold outcomes constant across conditions or make outcome a deliberate factor. A pretest comparing your conditions question-by-question will show whether an outcome reveal is leaking into unrelated DVs.",
    related: ["sunk-cost-fallacy", "myside-bias", "omission-bias"],
  },
  {
    slug: "allais-paradox",
    name: "Allais paradox",
    title: "What is the Allais paradox?",
    description:
      "The Allais paradox: the certainty effect that breaks expected utility theory, explained with the classic two-gamble problem and AI replication results.",
    status: "yes",
    definition:
      "The Allais paradox is a pair of lottery choices in which most people's preferences contradict expected utility theory. People overweight certainty: they'll sacrifice expected value to lock in a sure thing, but when both options are risky, the same people switch to chasing the bigger prize.",
    classicStudy:
      "Allais (1953) offered: Problem 1 — $1M for sure, versus a gamble with 10% at $5M, 89% at $1M, and 1% at nothing; most take the sure million. Problem 2 — an 11% chance at $1M versus a 10% chance at $5M; most take the 10% shot at $5M. Under expected utility, choosing safe in Problem 1 requires choosing safe in Problem 2 — the combination violates the theory.",
    example:
      "Insurance decisions (paying premiums to eliminate small risks entirely), promotion designs ('guaranteed prize' versus a larger long-shot), and any choice architecture where certainty is on the menu.",
    aiResult:
      "Reproduced emphatically: 98.6% of AI respondents chose the certain option in Problem 1 while 94.6% chose the riskier gamble in Problem 2 (χ² = 252, p < .001, N ≈ 147 per problem), producing the paradoxical pattern in every model in the ensemble.",
    surveyTip:
      "Choices involving certainty behave differently from choices between risks — a 100% option is qualitatively special, not just the end of a probability scale. If your design includes certain outcomes, pretest whether your effect survives when the certainty is replaced with 99%.",
    related: ["framing-effect", "probability-matching", "dominance-neglect"],
  },
  {
    slug: "base-rate-neglect",
    name: "Base-rate neglect",
    title: "What is base-rate neglect?",
    description:
      "Base-rate neglect: Kahneman & Tversky's engineer–lawyer problem, why vivid descriptions trump statistics, and AI respondent replication data.",
    status: "yes",
    definition:
      "Base-rate neglect is under-weighting statistical background information (how common something is) in favor of individuating details (how representative a description feels). A vivid personality sketch swamps the odds.",
    classicStudy:
      "Kahneman and Tversky (1973) told participants that a panel contained either 30 engineers and 70 lawyers, or 70 engineers and 30 lawyers, then shared a description of 'Jack,' who sounds stereotypically like an engineer. Probability judgments that Jack is an engineer barely moved with the base rate — the description did nearly all the work.",
    example:
      "A hiring manager who reads one vivid reference letter and ignores that 95% of applicants from that pool succeed; survey respondents judging how likely a described person is to buy a niche product while ignoring how rare the product's buyers are.",
    aiResult:
      "Reproduced. AI respondents given the engineer-sounding sketch estimated 69.3% 'engineer' even when engineers were only 30% of the panel, rising just ~12 points (to 81.0%) when the base rate jumped to 70% — far less movement than the base rates warrant (t = 7.2, p < .001, N = 150 per condition). Every model showed the pattern: the sketch dominates the statistics.",
    surveyTip:
      "When your instrument mixes statistical information with narrative detail, expect the narrative to win. If respondents are supposed to use the numbers you provide, pretest whether they actually do — a manipulation of base rates that nobody registers is a very common silent failure.",
    related: ["conjunction-fallacy", "anchoring-effect", "false-consensus-effect"],
  },
  {
    slug: "false-consensus-effect",
    name: "False consensus effect",
    title: "What is the false consensus effect?",
    description:
      "The false consensus effect: why people overestimate how widely their own views are shared, with the Ross, Greene & House citation and AI replication data.",
    status: "yes",
    definition:
      "The false consensus effect is overestimating how many other people share your own beliefs, preferences, and behaviors. Your own position feels like common sense, so estimates of public opinion get pulled toward it.",
    classicStudy:
      "Ross, Greene, and House (1977) asked students to make a choice (famously, whether they'd walk around campus wearing a sandwich board), then estimate what percentage of peers would make the same choice. Whichever option people chose, they believed a majority of others would choose it too.",
    example:
      "Respondents who support a policy estimate public support 20 points higher than opponents do — on the same policy, in the same sample. This contaminates any item that asks people to estimate norms, market size, or 'what most people think.'",
    aiResult:
      "Reproduced. Across four contested issues (abortion, gun control, immigration, climate change), AI respondents' own agreement correlated with their estimates of public agreement at r = 0.17 (p < .001 across 597 respondent–item pairs) — modest, as in humans, and present in every model.",
    surveyTip:
      "Norm-estimation items ('what % of people like you…') measure the respondent as much as the norm. If your study uses them as a DV, consider also measuring the respondent's own position so you can model the consensus bias instead of absorbing it as noise.",
    related: ["myside-bias", "base-rate-neglect", "conjunction-fallacy"],
  },
  {
    slug: "probability-matching",
    name: "Probability matching",
    title: "What is probability matching?",
    description:
      "Probability matching vs. maximizing: the classic prediction task where people match frequencies instead of always betting the favorite, with AI replication data.",
    status: "yes",
    definition:
      "Probability matching is predicting random outcomes in proportion to their frequencies — guessing 'red' 70% of the time when red occurs 70% of the time — instead of the optimal strategy of always predicting the most likely outcome. Matching feels responsive to the pattern but guarantees more errors than maximizing.",
    classicStudy:
      "In the classic paradigm (reviewed by Vulkan, 2000; used by Stanovich & West, 2008), participants predict a light that flashes red 70% and green 30% of the time. A maximizer predicts red every trial and is right 70% of the time; a matcher mixes 70/30 and is right only 58% of the time. A substantial share of people match anyway.",
    example:
      "Investors spreading bets across options in proportion to past success rather than concentrating on the best option; respondents in repeated-choice product tests 'rotating' their picks to mirror perceived popularity.",
    aiResult:
      "Reproduced at the ensemble level (p < .001 on the shift toward matching), though with real model variation: two of the five models produced matching behavior while the rest maximized nearly perfectly. Like the other optimality-flavored tasks in our benchmark, this is a bias some models reason their way out of.",
    surveyTip:
      "In repeated or multi-trial designs, don't assume respondents play the optimal strategy — and don't assume AI pretest respondents will deviate from it the way humans do. For strategy-dependent designs, check the AI result per model, not just on average.",
    related: ["allais-paradox", "dominance-neglect", "base-rate-neglect"],
  },
  {
    slug: "affect-heuristic",
    name: "Risk–benefit nonseparability",
    title: "The affect heuristic: why risk and benefit judgments are linked",
    description:
      "Risk–benefit nonseparability and the affect heuristic: Alhakami & Slovic's finding that liking something lowers its perceived risk, with AI replication data.",
    status: "yes",
    definition:
      "In the world, risk and benefit tend to be positively correlated — valuable activities often carry real dangers. In people's heads, they're negatively correlated: things we like (favorite technologies, familiar activities) are judged both high-benefit and low-risk, while things we dislike get the reverse. This is the signature of the affect heuristic — a single good/bad feeling driving both judgments.",
    classicStudy:
      "Alhakami and Slovic (1994) had participants rate the risks and benefits of items like nuclear power, pesticides, alcohol, and X-rays. Within respondents, risk and benefit judgments were negatively correlated — liking drove both numbers rather than independent analysis of each.",
    example:
      "A consumer who loves a brand rates its products as safer; a respondent enthusiastic about AI rates its societal risk lower. Any survey asking for both risk and benefit ratings of the same object will find them entangled.",
    aiResult:
      "Reproduced by the ensemble, narrowly: mean within-respondent correlation of −0.24 across six hazards (p = .046), with four of six items individually negative — but only one of the five models reproduced it on its own. Affect-driven judgment is at the edge of what current AI respondents show.",
    surveyTip:
      "If you measure perceived risk and perceived benefit as separate constructs, expect them to share an affective core — and treat an AI pretest of affect-driven effects as suggestive rather than decisive, since this is one of the hardest biases for models to express.",
    related: ["less-is-more-effect", "myside-bias", "outcome-bias"],
  },
  {
    slug: "omission-bias",
    name: "Omission bias",
    title: "What is omission bias?",
    description:
      "Omission bias: why harm from action feels worse than identical harm from inaction, with the classic vaccination paradigm and AI replication data.",
    status: "yes",
    definition:
      "Omission bias is judging harmful actions as worse than equally harmful inactions. Causing harm by doing something feels more blameworthy — and more avoidable — than allowing the same harm by doing nothing, even when the outcomes are identical.",
    classicStudy:
      "In the vaccination paradigm (Spranca, Minsk & Baron, 1991), parents face a disease that will kill 10 in 10,000 unvaccinated children, and a vaccine that prevents the disease but itself kills 10 in 10,000 — identical risk either way. A rational decision-maker is indifferent; many people refuse the vaccine, because a death caused by their action weighs more than one caused by their inaction.",
    example:
      "Clinicians more willing to withhold treatment than to administer one with identical risk; consumers who won't switch to an objectively equal product because switching is an act; policy survey respondents punishing active harms over equivalent passive ones.",
    aiResult:
      "Reproduced at the ensemble level with a dramatic split: 67.1% of AI respondents refused the vaccine when refusal was framed as their own action's consequence versus 0% under the inaction frame (χ² = 148, p < .001, N ≈ 150 per condition) — but only one of the five models produced it. (We redesigned the item so both conditions hold outcomes constant; see the technical report.) Most models computed the equal risks and chose indifference.",
    surveyTip:
      "Action/inaction framing is a potent manipulation that's easy to introduce by accident — 'would you switch?' and 'would you keep?' are not the same question. Pretest both framings of any choice DV, and read per-model AI results for action-framing effects rather than the ensemble average.",
    related: ["outcome-bias", "framing-effect", "sunk-cost-fallacy"],
  },
  {
    slug: "endowment-effect",
    name: "Endowment effect",
    title: "What is the endowment effect? WTA vs. WTP",
    description:
      "The endowment effect and the WTA–WTP gap: why owners demand more than buyers will pay, with Thaler's classic account and partial AI replication data.",
    status: "partial",
    definition:
      "The endowment effect is valuing a thing more simply because you own it. The signature is the WTA–WTP gap: the minimum owners are willing to accept to give something up reliably exceeds what equivalent non-owners are willing to pay to get it.",
    classicStudy:
      "Thaler (1980) named the effect, and the lottery-ticket version (used by Stanovich & West, 2008) measures it cleanly: people endowed with a lottery ticket demand more to sell it than identical participants will pay to buy the same ticket, with a further drop in willingness to pay when the lottery's outcome is uncertain.",
    example:
      "Kahneman, Knetsch and Thaler's famous mugs: students given a mug demanded about twice as much to sell it as other students would pay to buy it. In practice: free-trial pricing, returns behavior, and any survey measuring valuations from an 'owner' versus 'chooser' perspective.",
    aiResult:
      "Partially reproduced — the honest half-point in our 15.5/17. AI owners demanded more (WTA M = $30.1) than buyers would pay (WTP M = $25.0; t = 16.1, p < .001), so the core ownership premium is there in every model. But the full three-way ordering the paradigm predicts (including the risky-lottery condition) did not emerge. Ownership framing moves AI respondents; the complete human pattern doesn't.",
    surveyTip:
      "Valuation questions must fix the respondent's role: owners, buyers, and choosers give different numbers for identical goods. If your pricing study mixes WTA and WTP item framings, that's a confound a pretest will catch — and for full endowment designs, weight human pilot data more heavily.",
    related: ["sunk-cost-fallacy", "relative-savings", "less-is-more-effect"],
  },
  {
    slug: "dominance-neglect",
    name: "Dominance neglect",
    title: "Dominance neglect: the bias AI respondents don't show",
    description:
      "Dominance neglect: Tversky & Kahneman's masked-dominance gamble that ~40% of humans get wrong — and that AI respondents solve almost perfectly. The clearest limit of AI pretesting.",
    status: "no",
    definition:
      "Dominance neglect is failing to notice that one option is better than another in every possible outcome when the dominance is masked by the way options are described. Transparent dominance is easy — nobody picks the obviously worse option — but light disguise (regrouping outcomes, changing labels) hides it from a large share of people.",
    classicStudy:
      "In Tversky and Kahneman's (1986) marble gamble (also in Stanovich & West, 2008), two payoff schemes over colored marbles are constructed so one option is state-by-state at least as good and strictly better in two states — but the framing masks it. Roughly 40% of human participants choose the dominated option.",
    example:
      "Insurance or subscription tiers where one plan quietly dominates another, yet the dominated plan keeps selling; A/B tests where a strictly better bundle loses because its superiority is spread across hard-to-compare components.",
    aiResult:
      "Not reproduced — the clearest failure in our benchmark, and we think the most instructive. Across every model in the ensemble, only 0.7–1.4% of AI respondents chose the dominated option, versus roughly 40% of humans. The models simply compute the payoffs and spot the dominance. Where a bias depends on people missing something, AI respondents are too rational.",
    surveyTip:
      "This is the boundary of AI pretesting, stated plainly: if your effect requires respondents to overlook information that careful analysis would reveal, do not expect AI respondents to overlook it. Pretest the plumbing and the manipulation, but take effects built on inattention or masked structure to human pilots early.",
    related: ["less-is-more-effect", "probability-matching", "allais-paradox"],
  },
];

export function getBias(slug: string): Bias | undefined {
  return BIASES.find((b) => b.slug === slug);
}
