# Reproducible metadata comparison

This file is generated offline. The separately authored report.md interprets the captured experiment.

Primary metrics exclude supplements, user scenarios and borderline reference labels.

| Method | TP | FP | FN | Precision | Recall | Region correct / checked |
|---|---:|---:|---:|---:|---:|---:|
| deterministic | 5 | 2 | 0 | 71.4% | 100.0% | 13/14 |
| deterministic_gate | 5 | 2 | 0 | 71.4% | 100.0% | 13/14 |
| luna-100 | 5 | 2 | 0 | 71.4% | 100.0% | 14/14 |
| luna-repartitioned | 5 | 2 | 0 | 71.4% | 100.0% | 14/14 |

## primary

Legacy: R=retained, X=excluded/deferred. LLM: decision, relevance, region, diagnostic rank. Unknown dates remain null. Diagnostic ranks are not production queue scores.

| ID / title | Reference / acceptable regions | Legacy decision / region / rank | luna-100 | luna-repartitioned |
|---|---|---|---|---|
| rss-00: Syria’s central bank issues first letter of credit in 14 years | Irrelevant; not scored | R (); Global; rank 7 | Irrelevant 1; Global; rank - | Irrelevant 1; Global; rank - |
| rss-01: Acwa to consider solar and wind projects in Mongolia | Borderline; Out of Scope/Unclear | R (); KSA; rank 1 | Borderline 3; Out of Scope/Unclear; rank 1 | Irrelevant 1; Out of Scope/Unclear; rank - |
| rss-02: QatarEnergy reveals steep fall in profit and revenue | Borderline; Global | R (); Global; rank 8 | Irrelevant 1; Global; rank - | Borderline 2; Global; rank 7 |
| rss-03: Adia backs IPO of India’s Zetwerk as anchor investor | Irrelevant; not scored | X (no company-topic match); UAE; rank - | Irrelevant 1; Out of Scope/Unclear; rank - | Irrelevant 1; Out of Scope/Unclear; rank - |
| rss-04: Mubadala’s GlobalFoundries lands $21bn US chip project | Irrelevant; not scored | X (no company-topic match); UAE; rank - | Irrelevant 1; Out of Scope/Unclear; rank - | Irrelevant 1; Out of Scope/Unclear; rank - |
| rss-05: Qatar companies get grant to offset higher shipping costs | Borderline; Global | X (shortlist ceiling); Global; rank 9 | Irrelevant 1; Global; rank - | Borderline 2; Global; rank 8 |
| rss-06: US plans to ease sanctions on shadow fleet | Irrelevant; not scored | X (no exact target region); Unclear; rank - | Irrelevant 1; Global; rank - | Irrelevant 1; Out of Scope/Unclear; rank - |
| rss-07: Demand destruction: an indelicate forecast | Irrelevant; not scored | R (); KSA; rank 3 | Irrelevant 1; KSA; rank - | Borderline 2; KSA; rank 2 |
| rss-08: State spending cushions Gulf projects from war | Irrelevant; not scored | X (no company-topic match); Global; rank - | Borderline 2; Global; rank 5 | Borderline 2; Global; rank 9 |
| rss-09: Two vessels sink off Oman as Hormuz attacks intensify | Borderline; Global | X (shortlist ceiling); Global; rank 10 | Borderline 2; Global; rank 6 | Borderline 3; Global; rank 5 |
| oct16-negation: Not AI. Not energy. Not water. Mohammed bin Rashid says the currency of the future is trust - Gulf News | Irrelevant; not scored | X (no company-topic match); UAE; rank - | Irrelevant 1; UAE; rank - | Irrelevant 1; UAE; rank - |
| oct16-battery_definition: Your battery may not be a battery - Nature | Irrelevant; not scored | X (battery coverage without a transition application); Global; rank - | Borderline 2; Out of Scope/Unclear; rank 3 | Irrelevant 1; Global; rank - |
| oct16-battery_science: Evidence for multi-Li+ clustering in lithium-ion battery electrolytes - Nature | Borderline; Out of Scope/Unclear, Global | X (battery coverage without a transition application); Global; rank - | Borderline 2; Out of Scope/Unclear; rank 4 | Irrelevant 1; Global; rank - |
| oct16-crypto: Standard Chartered licensed to launch crypto trading in UAE - Arabian Gulf Business Insight &#124; AGBI | Irrelevant; not scored | X (consumer finance or passenger travel without a direct mission consequence); UAE; rank - | Irrelevant 1; UAE; rank - | Irrelevant 1; UAE; rank - |
| oct16-flights: Flying from the UAE this weekend? Saudi flights face major disruption as cancellations mount - Gulf News | Irrelevant; not scored | X (consumer finance or passenger travel without a direct mission consequence); Unclear; rank - | Irrelevant 1; KSA; rank - | Irrelevant 1; KSA; rank - |
| oct16-commission: Saudi Arabia Wins Two International Commission on Irrigation and Drainage Awards in France - وكالة الأنباء السعودية | Borderline; Out of Scope/Unclear, KSA | R (); KSA; rank 2 | Borderline 3; KSA; rank 1 | Borderline 3; KSA; rank 1 |
| oct16-veal: Egypt's minister approves new funding for National Veal Project - Zawya | Relevant; Egypt | R (); Egypt; rank 1 | Relevant 4; Egypt; rank 2 | Relevant 4; Egypt; rank 2 |
| oct16-gerd: GERD Explained 2026: Ethiopia, Egypt and the Nile Dam Dispute | Borderline; Global, Egypt | R (); Egypt; rank 2 | Relevant 5; Egypt; rank 1 | Relevant 5; Egypt; rank 1 |
| oct16-harvests: Hormuz shipping disruption is starting to hit harvests, UN agency says - Arab News | Relevant; Global | R (); Global; rank 5 | Relevant 5; Global; rank 1 | Relevant 5; Global; rank 2 |
| oct16-iraq: Iraq in talks with Saudi’s Acwa to increase solar capacity - Arabian Gulf Business Insight &#124; AGBI | Relevant; Global | R (); Global; rank 4 | Relevant 4; Global; rank 4 | Relevant 5; Global; rank 1 |
| oct16-libya: Flooded streets, damage in Libya as heavy rains paralyze capital - Arab News | Borderline; Global | R (); Global; rank 6 | Borderline 2; Global; rank 7 | Borderline 3; Global; rank 6 |
| oct16-qatar: Qatar’s renewable energy share set to more than double by 2035 - Fast Company Middle East | Relevant; Global | R (); Global; rank 3 | Relevant 5; Global; rank 3 | Relevant 5; Global; rank 4 |
| oct15-istanbul: Heavy rain and flooding in Istanbul forces closure of schools - Arab News | Irrelevant; not scored | X (outside geographic mandate); Unclear; rank - | Irrelevant 1; Global; rank - | Irrelevant 1; Out of Scope/Unclear; rank - |
| oct15-hormuz: Failure to activate Hormuz fertilizer plan could trigger food crisis, UN official says - Arab News | Relevant; Global | R (); Global; rank 2 | Relevant 5; Global; rank 2 | Relevant 5; Global; rank 3 |
| oct15-bahrain: Bahraini fund to invest in power grids across US and Europe - Arabian Gulf Business Insight &#124; AGBI | Borderline; Out of Scope/Unclear, Global | R (); Global; rank 1 | Borderline 2; Out of Scope/Unclear; rank 2 | Irrelevant 2; Out of Scope/Unclear; rank - |

## supplemental

Legacy: R=retained, X=excluded/deferred. LLM: decision, relevance, region, diagnostic rank. Unknown dates remain null. Diagnostic ranks are not production queue scores.

| ID / title | Reference / acceptable regions | Legacy decision / region / rank | luna-100 | luna-repartitioned |
|---|---|---|---|---|
| saved-sharjah: 410,000 m³ of water a day, 35 more years at the ports and 600,000 tonnes of waste capacity: Investing in Sharjah's next growth cycle - Khaleej Times | Relevant; UAE | X (unknown publication date); UAE; rank - | Relevant 5; UAE; rank - | Relevant 5; UAE; rank - |
| saved-egypt-battery: Egypt to get new lithium-ion battery assembly facility - Zawya | Relevant; Egypt | X (unknown publication date); Egypt; rank - | Relevant 4; Egypt; rank - | Relevant 4; Egypt; rank - |
| user-west-bank: 'He irrigated the tree with his blood': West Bank olive farmers set for another deadly harvest | Borderline; Global | X (no usable URL); Unclear; rank - | Borderline 2; Global; rank - | Borderline 2; Global; rank - |

## diagnostic

Legacy: R=retained, X=excluded/deferred. LLM: decision, relevance, region, diagnostic rank. Unknown dates remain null. Diagnostic ranks are not production queue scores.

| ID / title | Reference / acceptable regions | Legacy decision / region / rank | luna-100 | luna-repartitioned |
|---|---|---|---|---|
| diagnostic-uae-strategy: UAE food-production strategy | Relevant; UAE | X (no usable URL); UAE; rank - | Relevant 4; UAE; rank - | Relevant 4; UAE; rank - |
| diagnostic-egypt-green: Egypt green industrialisation, subject to novelty and evidence | Borderline; Egypt | X (no usable URL); Egypt; rank - | Borderline 3; Egypt; rank - | Borderline 3; Egypt; rank - |
| diagnostic-saudi-weather: Routine Saudi weather forecasts | Irrelevant; not scored | X (no usable URL); KSA; rank - | Irrelevant 1; KSA; rank - | Irrelevant 1; KSA; rank - |
| diagnostic-landscape: Agricultural landscape descriptions | Irrelevant; not scored | X (no usable URL); Unclear; rank - | Irrelevant 1; Out of Scope/Unclear; rank - | Irrelevant 1; Out of Scope/Unclear; rank - |
| diagnostic-economy: Generic economic news mentioning energy | Irrelevant; not scored | X (no usable URL); Unclear; rank - | Irrelevant 1; Out of Scope/Unclear; rank - | Irrelevant 1; Out of Scope/Unclear; rank - |
| diagnostic-water-science: Water-related laboratory papers without a demonstrated mission application | Borderline; Out of Scope/Unclear, Global | X (no usable URL); Unclear; rank - | Borderline 2; Out of Scope/Unclear; rank - | Borderline 2; Out of Scope/Unclear; rank - |
| diagnostic-foreign-water: Foreign-local water infrastructure projects without a MENA or systemic bridge | Irrelevant; not scored | X (no usable URL); Unclear; rank - | Irrelevant 1; Out of Scope/Unclear; rank - | Irrelevant 1; Out of Scope/Unclear; rank - |

## Reference and model rationales

**rss-00**: Petroleum trade/banking resumption; no supported food, water or transition consequence.

- luna-100: The story concerns Syria's petroleum-product imports and trade access, with no supported food, water or net-zero connection.
- luna-repartitioned: The story concerns Syria resuming trade finance for petroleum imports, with no supported food, water or net-zero transition connection.

**rss-01**: Concrete renewables/export proposal abroad with a Saudi company; credible commercial MENA bridge but foreign project, not KSA geography.

- luna-100: A large Mongolia solar, wind and storage proposal is transition-related, but it is foreign-local and no MENA or systemic bridge is shown.
- luna-repartitioned: The solar, wind and storage project is in Mongolia and targets electricity exports to China; no MENA or systemic connection is established.

**rss-02**: Major LNG operational disruption in MENA; indirect transition/security consequences unspecified.

- luna-100: QatarEnergy's reported financial decline and LNG disruption concern fossil-fuel business, without a supported mission connection.
- luna-repartitioned: Conflict disrupted Qatar’s LNG export capacity, a significant regional energy event, but the metadata does not establish a net-zero transition connection.

**rss-03**: Generic industrial IPO investment; no explicit mission application.

- luna-100: An Abu Dhabi fund's investment in an Indian manufacturer has no stated food, water or net-zero relevance.
- luna-repartitioned: An Abu Dhabi fund’s investment in an Indian manufacturer is described without a food, water or net-zero mission link.

**rss-04**: Semiconductor investment without a demonstrated mission application.

- luna-100: The US semiconductor project has no supported food, water or net-zero connection; the investor's nationality is not a project bridge.
- luna-repartitioned: The chipmaker’s planned manufacturing plants are in New York; no food, water or net-zero connection is stated.

**rss-05**: Regional logistics support could cover mission supply chains, but sectors unspecified; preserve uncertainty.

- luna-100: The grant offsets shipping costs for Qatar manufacturers generally; no mission-critical goods or consequence are identified.
- luna-repartitioned: Qatar is subsidizing manufacturers’ shipping costs, but the materials and affected industries are unspecified, leaving any mission impact unclear.

**rss-06**: Oil-fleet sanctions/prices without a demonstrated mission consequence.

- luna-100: The item concerns oil-shipping sanctions and crude prices, with no supported food, water or net-zero transition link.
- luna-repartitioned: The reported US policy concerns oil-shipping sanctions and freight rates, with no supported food, water or net-zero transition connection.

**rss-07**: Hydrocarbon export commentary without a supported mission development.

- luna-100: The focus is Saudi hydrocarbon exports and pipeline alternatives, without a supported net-zero or other mission connection.
- luna-repartitioned: Saudi Arabia is considering pipeline changes to address export constraints, but the described focus is hydrocarbons, not a stated net-zero transition.

**rss-08**: Broad contracts/spending update; energy alone does not establish transition relevance.

- luna-100: Gulf energy and transport spending is mentioned, but project types and any food, water or net-zero relevance are unspecified.
- luna-repartitioned: Gulf governments sustained energy and transport project spending, but no specific food, water or net-zero projects are identified.

**rss-09**: Material Hormuz disruption, but cargo/agricultural effects unspecified; potential indirect mission bridge.

- luna-100: Attacks near the Hormuz chokepoint could affect mission-relevant shipping, but the cargoes or food, water and energy impacts are not stated.
- luna-repartitioned: Attacks sank two vessels near the Strait of Hormuz, but their cargoes and any resulting food, fertilizer or other mission-related disruption are unspecified.

**oct16-negation**: Trust commentary expressly disclaims energy/water; incidental keywords.

- luna-100: The title explicitly says the subject is not energy or water and offers no other mission connection.
- luna-repartitioned: The title explicitly frames the remarks around trust, not water or energy, and gives no food-security or net-zero connection.

**oct16-battery_definition**: Battery definition commentary; no demonstrated practical mission application.

- luna-100: The title suggests battery-related discussion, but gives no applied transition relevance, project or MENA connection.
- luna-repartitioned: The title suggests a battery-related discussion but gives no applied energy-storage or net-zero consequence.

**oct16-battery_science**: Plausible storage application but no demonstrated deployment; not high relevance.

- luna-100: This is lithium-ion electrolyte science; no applied battery advance or transition consequence is stated.
- luna-repartitioned: The title describes electrolyte research without evidence of an applied storage or net-zero consequence.

**oct16-crypto**: Crypto trading license without a mission consequence.

- luna-100: Crypto trading licensing has no supported connection to the mission.
- luna-repartitioned: Crypto-trading licensing has no stated food, water or net-zero connection.

**oct16-flights**: Passenger cancellations without a mission consequence.

- luna-100: Flight cancellations are reported without a food, water or net-zero link.
- luna-repartitioned: Flight cancellations are reported without a supported food, water or net-zero consequence.

**oct16-commission**: Irrigation awards in France; possible Saudi application but operational consequences unknown. Not a new Saudi project.

- luna-100: Saudi irrigation and drainage awards point to water-management relevance, but the title does not say what was awarded or its practical impact.
- luna-repartitioned: Irrigation and drainage awards suggest a water-management connection, but the awarded work and its practical significance are not described.

**oct16-veal**: New national livestock funding directly supports Egyptian agricultural capacity.

- luna-100: New funding for Egypt's National Veal Project supports livestock production; the scale and expected food-supply effect are not stated.
- luna-repartitioned: New funding for Egypt’s National Veal Project directly supports livestock production; the project’s scale and expected output are unspecified.

**oct16-gerd**: Central Nile water-security topic, but explainer novelty and event geography unresolved.

- luna-100: The Ethiopia-Egypt Nile dam dispute directly concerns transboundary water security and Egypt's water interests.
- luna-repartitioned: The Ethiopia–Egypt Nile dam dispute directly concerns shared water resources and Egypt's water security.

**oct16-harvests**: Explicit shipping-to-harvest production consequence; systemic food security.

- luna-100: The title explicitly links Hormuz shipping disruption to harvest impacts, indicating a direct food-production consequence.
- luna-repartitioned: The title explicitly links Hormuz shipping disruption to impacts on harvests, a direct food-production concern.

**oct16-iraq**: Solar expansion talks in Iraq; Saudi nationality is not project geography.

- luna-100: Talks to increase Iraq's solar capacity are a direct renewable-energy development; the project remains at discussion stage.
- luna-repartitioned: Talks to increase solar capacity in Iraq are a direct renewable-energy development.

**oct16-libya**: Consequential regional flooding; mission infrastructure/food effects unspecified.

- luna-100: Severe rain and urban flooding are reported, but no food- or water-security consequence is specified.
- luna-repartitioned: Heavy rain caused flooding and paralysis in Libya’s capital, but the metadata does not establish wider water-security, infrastructure or agricultural impacts.

**oct16-qatar**: Potential material renewable share change in other MENA; assess forecast versus funded commitment later.

- luna-100: Qatar's renewable-energy share is set to more than double by 2035, a clear transition target.
- luna-repartitioned: Qatar’s renewable energy share is projected to more than double by 2035, a direct energy-transition development.

**oct15-istanbul**: School closures in Turkey without a demonstrated mission infrastructure or food effect.

- luna-100: The title reports local flooding and school closures, with no supported food- or water-security consequence.
- luna-repartitioned: The Istanbul flooding is reported as causing school closures; no food- or water-security consequence is stated.

**oct15-hormuz**: Fertilizer-plan failure explicitly threatens food availability; distinct from observed harvest losses.

- luna-100: Failure to activate a Hormuz fertilizer plan is explicitly linked to risk of a food crisis, a systemic food-security concern.
- luna-repartitioned: Failure of a Hormuz fertilizer plan is explicitly linked to a potential food crisis, a consequential food-security risk.

**oct15-bahrain**: MENA grid investment abroad could enable transition, but technology/purpose absent. Not a Bahrain project.

- luna-100: A Bahraini fund plans grid investments in the US and Europe, but the title gives no clean-energy or MENA project connection.
- luna-repartitioned: The stated grid investments are in the US and Europe; no MENA or net-zero connection is established.

**saved-sharjah**: Explicit large water/waste capacity and investment in Sharjah.

- luna-100: The title identifies 410,000 m³/day of water capacity in Sharjah, a substantial direct water-infrastructure development.
- luna-repartitioned: The Sharjah investment plans cite water capacity of 410,000 m³ per day, a direct water-infrastructure development.

**saved-egypt-battery**: Practical lithium-ion assembly capacity development in Egypt.

- luna-100: A lithium-ion battery assembly facility in Egypt is a direct energy-storage industrial development; scale and intended use are unspecified.
- luna-repartitioned: A lithium-ion battery assembly facility in Egypt is a direct energy-transition manufacturing development; its intended applications and scale are not given.

**user-west-bank**: Violence against farmers is not proof of food-system disruption; sparse title merits caution, never high relevance from agriculture alone.

- luna-100: The story concerns olive farmers and harvest season, but the title does not establish that violence disrupts production or food availability.
- luna-repartitioned: The story concerns violence against West Bank olive farmers during harvest, but the metadata does not show effects on harvests or food production.

**diagnostic-uae-strategy**: Potential direct strategic food-capacity relevance; novelty/importance unresolved.

- luna-100: A UAE food-production strategy is directly tied to domestic food-production capacity; details and scale are not specified.
- luna-repartitioned: A UAE food-production strategy is directly connected to food security, though its measures and scale are unspecified.

**diagnostic-egypt-green**: Potential industrial transition relevance; no specific new development supplied.

- luna-100: Egyptian green industrialisation could relate to the transition, but the specific development and its novelty or evidence are not provided.
- luna-repartitioned: Egyptian green industrialisation could relate to the transition, but the metadata gives no project details or evidence of a material development.

**diagnostic-saudi-weather**: Ordinary forecast with no demonstrated mission consequence.

- luna-100: Routine weather forecasts provide no supported food, water-security or net-zero consequence.
- luna-repartitioned: Routine weather forecasts have no stated food- or water-security consequence.

**diagnostic-landscape**: Scenery without a mission development.

- luna-100: Agricultural landscape description alone gives no food-security development or consequence.
- luna-repartitioned: Agricultural landscape descriptions alone do not establish a food-security development or consequence.

**diagnostic-economy**: Energy keyword alone is insufficient.

- luna-100: Generic economic news only mentions energy; no supported food, water or net-zero connection.
- luna-repartitioned: Generic economic coverage only mentions energy; no supported connection to food, water or the net-zero transition.

**diagnostic-water-science**: Not high relevance; potential application cannot be assessed from this generic description.

- luna-100: Water research is indicated, but no practical application or mission consequence is demonstrated.
- luna-repartitioned: Water research may have mission relevance, but no application or project geography is provided.

**diagnostic-foreign-water**: Explicitly foreign-local without a regional/systemic link.

- luna-100: The title explicitly describes foreign-local water projects without a MENA or systemic bridge.
- luna-repartitioned: Foreign-local water infrastructure with no stated MENA or systemic bridge.
