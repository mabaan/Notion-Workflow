# Candidate geography and eligibility policy

This document describes the legacy `deterministic` mode. In opt-in `luna` mode, objective cleanup precedes metadata classification; classifier event geography replaces these keyword/source-fallback heuristics, and coverage targets permit a second overflow pass. See [controlled Luna selection](luna_selection.md).

The four quota labels and weekly targets remain Global 3, UAE 4, KSA 3 and Egypt 2. Geography controls routing; all candidates still pass the existing freshness, relevance, deduplication, publisher-cap and human-review rules.

## Project geography, participants and publishers

Use the reported project/event location from the headline, then the description. Explicit project sites take priority over the nationality of a contractor or investor. Nationality constructions such as “Saudi's Acwa”, “UAE-based company” and “Saudi firm” do not by themselves establish a project location. A headline's publisher suffix does not establish article geography either. Unresolved country ties remain unassigned rather than defaulting to UAE.

| Evidence | Quota routing |
|---|---|
| Project/event in UAE, Saudi Arabia or Egypt | Corresponding country quota |
| Relevant project/event in another MENA country, including Qatar, Iraq or Libya | Global; audit explicitly records the actual location and “other MENA” basis |
| Explicit systemic mission development, such as global food-supply disruption | Global; “Global” alone or publisher reputation is insufficient |
| Foreign local news without an explicit MENA mission bridge | Reject geographically |
| No article geography, RSS publisher supplies a regional hint | Existing source-region fallback, identified as such in the audit |
| No article geography, discovery query supplies a regional hint | Unassigned; a search query is not evidence of article location |

“Global” is the existing bucket for systemic international developments **and other-MENA coverage outside the three country quotas**. It is not a claim that every routed article has worldwide impact. Routing Iraqi solar discussions to Global does not count them as Saudi projects merely because a Saudi company participates. Libya flooding does not count toward KSA because Arab News publishes it. These mappings introduce no new quota region and do not grant relevance qualification.

Location detection is deliberately a bounded metadata heuristic, not entity resolution. Other-MENA names and common nationality constructions are explicit; complex multi-country stories can remain ambiguous. Review the recorded assignment basis when deciding whether a story belongs in the newsletter.

## Narrow eligibility corrections

- Explicitly negated mission nouns do not supply direct relevance. “Not only water” and “not enough water” retain substantive water meaning.
- Battery materials/definition coverage needs a supported transition application, such as grid storage, manufacturing, deployment or a named battery asset. Independent food/water mission evidence remains usable. This gate does not exclude a scientific publisher or all research.
- Crypto finance and passenger travel need a direct mission consequence in the supplied metadata. Fertilizer delivery disruptions, solar-powered operations and similar explicit bridges remain eligible for normal enrichment.
- Veal/livestock production, harvest impacts and Nile/dam-dispute terminology can supply food/water signals without literally saying “food security” or “water security”. GERD medical coverage alone is not a water signal.
- The noun “Commission” does not imply newly commissioned infrastructure. Actual commissioning verbs still contribute development evidence.
- Content from `somamater.com` and its subdomains is excluded as independent input, including URL redirects discovered before enrichment. Other domains and independently published newsletters are not excluded by name.

## Attempts and audit explanations

Up to six initial attempts and eight total attempts per deficient region remain available. Failed LLM calls consume the budget; duplicates detected before the LLM call do not. The finite eligible pool can be checked for replacements until the unchanged attempt ceiling is reached. Replacement discovery candidates retain the reservation of up to two available discovery enrichment opportunities; remaining capacity can go to RSS.

The existing Markdown/JSON audits identify metadata rejection, geography/routing rejection, duplicate-before-enrichment, actual LLM attempts, relevance rejection, the stricter unregistered-publisher gate and final selection. Source/query hints are separate from assignment reasons. Evidence retrieval status and the existing significance rationale are recorded without extra model calls or article bodies. The original October 16 audit remains a historical record; it is not rewritten by this patch.
