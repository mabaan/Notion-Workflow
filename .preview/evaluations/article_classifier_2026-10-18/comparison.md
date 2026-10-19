# Reproducible metadata comparison

This file is generated offline. The separately authored report.md interprets the captured experiment.

Primary metrics exclude supplements, user scenarios and borderline reference labels.

| Method | TP | FP | FN | Precision | Recall | Region correct / checked |
|---|---:|---:|---:|---:|---:|---:|
| deterministic | 5 | 2 | 0 | 71.4% | 100.0% | 13/14 |
| deterministic_gate | 5 | 2 | 0 | 71.4% | 100.0% | 13/14 |
| mini-100 | 5 | 8 | 0 | 38.5% | 100.0% | 11/14 |
| mini-repartitioned | 5 | 8 | 0 | 38.5% | 100.0% | 11/14 |
| nano-100 | 5 | 6 | 0 | 45.5% | 100.0% | 12/14 |

## primary

Legacy: R=retained, X=excluded/deferred. LLM: decision, relevance, region, diagnostic rank. Unknown dates remain null. Diagnostic ranks are not production queue scores.

| ID / title | Reference / acceptable regions | Legacy decision / region / rank | mini-100 | mini-repartitioned | nano-100 |
|---|---|---|---|---|---|
| rss-00: Syria’s central bank issues first letter of credit in 14 years | Irrelevant; not scored | R (); Global; rank 7 | Relevant 4; Global; rank 1 | Borderline 2; Global; rank 11 | Borderline 3; Global; rank 5 |
| rss-01: Acwa to consider solar and wind projects in Mongolia | Borderline; Out of Scope/Unclear | R (); KSA; rank 1 | Relevant 4; Global; rank 2 | Relevant 4; Global; rank 1 | Borderline 3; Global; rank 6 |
| rss-02: QatarEnergy reveals steep fall in profit and revenue | Borderline; Global | R (); Global; rank 8 | Relevant 4; Global; rank 3 | Borderline 3; Global; rank 7 | Borderline 3; Global; rank 7 |
| rss-03: Adia backs IPO of India’s Zetwerk as anchor investor | Irrelevant; not scored | X (no company-topic match); UAE; rank - | Borderline 2; Out of Scope/Unclear; rank 3 | Borderline 2; Global; rank 12 | Borderline 2; Global; rank 11 |
| rss-04: Mubadala’s GlobalFoundries lands $21bn US chip project | Irrelevant; not scored | X (no company-topic match); UAE; rank - | Borderline 2; Out of Scope/Unclear; rank 4 | Borderline 2; Global; rank 13 | Borderline 3; Global; rank 8 |
| rss-05: Qatar companies get grant to offset higher shipping costs | Borderline; Global | X (shortlist ceiling); Global; rank 9 | Relevant 4; Global; rank 4 | Relevant 4; Global; rank 2 | Borderline 3; Global; rank 9 |
| rss-06: US plans to ease sanctions on shadow fleet | Irrelevant; not scored | X (no exact target region); Unclear; rank - | Borderline 3; Global; rank 9 | Borderline 3; Global; rank 8 | Borderline 2; Global; rank 12 |
| rss-07: Demand destruction: an indelicate forecast | Irrelevant; not scored | R (); KSA; rank 3 | Relevant 4; KSA; rank 3 | Relevant 4; KSA; rank 3 | Borderline 2; Global; rank 13 |
| rss-08: State spending cushions Gulf projects from war | Irrelevant; not scored | X (no company-topic match); Global; rank - | Relevant 4; Global; rank 5 | Relevant 4; Global; rank 3 | Borderline 2; Global; rank 14 |
| rss-09: Two vessels sink off Oman as Hormuz attacks intensify | Borderline; Global | X (shortlist ceiling); Global; rank 10 | Relevant 4; Global; rank 6 | Relevant 4; Global; rank 4 | Borderline 2; Global; rank 15 |
| oct16-negation: Not AI. Not energy. Not water. Mohammed bin Rashid says the currency of the future is trust - Gulf News | Irrelevant; not scored | X (no company-topic match); UAE; rank - | Irrelevant 1; UAE; rank - | Irrelevant 1; UAE; rank - | Irrelevant 1; Global; rank - |
| oct16-battery_definition: Your battery may not be a battery - Nature | Irrelevant; not scored | X (battery coverage without a transition application); Global; rank - | Borderline 2; Global; rank 11 | Borderline 2; Global; rank 10 | Irrelevant 1; Global; rank - |
| oct16-battery_science: Evidence for multi-Li+ clustering in lithium-ion battery electrolytes - Nature | Borderline; Out of Scope/Unclear, Global | X (battery coverage without a transition application); Global; rank - | Borderline 2; Global; rank 12 | Borderline 2; Global; rank 14 | Irrelevant 1; Global; rank - |
| oct16-crypto: Standard Chartered licensed to launch crypto trading in UAE - Arabian Gulf Business Insight &#124; AGBI | Irrelevant; not scored | X (consumer finance or passenger travel without a direct mission consequence); UAE; rank - | Irrelevant 1; UAE; rank - | Irrelevant 1; Out of Scope/Unclear; rank - | Irrelevant 1; Global; rank - |
| oct16-flights: Flying from the UAE this weekend? Saudi flights face major disruption as cancellations mount - Gulf News | Irrelevant; not scored | X (consumer finance or passenger travel without a direct mission consequence); Unclear; rank - | Irrelevant 1; UAE; rank - | Irrelevant 1; UAE; rank - | Irrelevant 1; Global; rank - |
| oct16-commission: Saudi Arabia Wins Two International Commission on Irrigation and Drainage Awards in France - وكالة الأنباء السعودية | Borderline; Out of Scope/Unclear, KSA | R (); KSA; rank 2 | Relevant 4; KSA; rank 4 | Relevant 4; KSA; rank 4 | Borderline 3; KSA; rank 1 |
| oct16-veal: Egypt's minister approves new funding for National Veal Project - Zawya | Relevant; Egypt | R (); Egypt; rank 1 | Relevant 4; Egypt; rank 2 | Relevant 4; Egypt; rank 2 | Borderline 2; Global; rank 17 |
| oct16-gerd: GERD Explained 2026: Ethiopia, Egypt and the Nile Dam Dispute | Borderline; Global, Egypt | R (); Egypt; rank 2 | Relevant 5; Egypt; rank 1 | Relevant 5; Egypt; rank 1 | Relevant 4; Egypt; rank 1 |
| oct16-harvests: Hormuz shipping disruption is starting to hit harvests, UN agency says - Arab News | Relevant; Global | R (); Global; rank 5 | Relevant 5; KSA; rank 1 | Relevant 5; KSA; rank 1 | Relevant 4; Global; rank 3 |
| oct16-iraq: Iraq in talks with Saudi’s Acwa to increase solar capacity - Arabian Gulf Business Insight &#124; AGBI | Relevant; Global | R (); Global; rank 4 | Relevant 4; Global; rank 7 | Relevant 4; Global; rank 5 | Relevant 4; Global; rank 2 |
| oct16-libya: Flooded streets, damage in Libya as heavy rains paralyze capital - Arab News | Borderline; Global | R (); Global; rank 6 | Borderline 3; Global; rank 10 | Borderline 3; Global; rank 9 | Borderline 2; Global; rank 16 |
| oct16-qatar: Qatar’s renewable energy share set to more than double by 2035 - Fast Company Middle East | Relevant; Global | R (); Global; rank 3 | Relevant 4; Global; rank 8 | Relevant 4; Global; rank 6 | Relevant 4; Global; rank 4 |
| oct15-istanbul: Heavy rain and flooding in Istanbul forces closure of schools - Arab News | Irrelevant; not scored | X (outside geographic mandate); Unclear; rank - | Borderline 3; Out of Scope/Unclear; rank 1 | Borderline 3; Out of Scope/Unclear; rank 1 | Irrelevant 1; Global; rank - |
| oct15-hormuz: Failure to activate Hormuz fertilizer plan could trigger food crisis, UN official says - Arab News | Relevant; Global | R (); Global; rank 2 | Relevant 5; KSA; rank 2 | Relevant 5; KSA; rank 2 | Relevant 5; Global; rank 1 |
| oct15-bahrain: Bahraini fund to invest in power grids across US and Europe - Arabian Gulf Business Insight &#124; AGBI | Borderline; Out of Scope/Unclear, Global | R (); Global; rank 1 | Borderline 2; Out of Scope/Unclear; rank 2 | Borderline 2; Out of Scope/Unclear; rank 2 | Borderline 2; Global; rank 10 |

## supplemental

Legacy: R=retained, X=excluded/deferred. LLM: decision, relevance, region, diagnostic rank. Unknown dates remain null. Diagnostic ranks are not production queue scores.

| ID / title | Reference / acceptable regions | Legacy decision / region / rank | mini-100 | mini-repartitioned | nano-100 |
|---|---|---|---|---|---|
| saved-sharjah: 410,000 m³ of water a day, 35 more years at the ports and 600,000 tonnes of waste capacity: Investing in Sharjah's next growth cycle - Khaleej Times | Relevant; UAE | X (unknown publication date); UAE; rank - | Relevant 4; UAE; rank - | Relevant 4; UAE; rank - | Borderline 2; Global; rank - |
| saved-egypt-battery: Egypt to get new lithium-ion battery assembly facility - Zawya | Relevant; Egypt | X (unknown publication date); Egypt; rank - | Relevant 4; Egypt; rank - | Relevant 4; Egypt; rank - | Borderline 3; Egypt; rank - |
| user-west-bank: 'He irrigated the tree with his blood': West Bank olive farmers set for another deadly harvest | Borderline; Global | X (no usable URL); Unclear; rank - | Borderline 2; Out of Scope/Unclear; rank - | Borderline 3; Global; rank - | Irrelevant 1; Out of Scope/Unclear; rank - |

## diagnostic

Legacy: R=retained, X=excluded/deferred. LLM: decision, relevance, region, diagnostic rank. Unknown dates remain null. Diagnostic ranks are not production queue scores.

| ID / title | Reference / acceptable regions | Legacy decision / region / rank | mini-100 | mini-repartitioned | nano-100 |
|---|---|---|---|---|---|
| diagnostic-uae-strategy: UAE food-production strategy | Relevant; UAE | X (no usable URL); UAE; rank - | Relevant 4; UAE; rank - | Relevant 4; UAE; rank - | Relevant 4; UAE; rank - |
| diagnostic-egypt-green: Egypt green industrialisation, subject to novelty and evidence | Borderline; Egypt | X (no usable URL); Egypt; rank - | Relevant 4; Egypt; rank - | Relevant 4; Egypt; rank - | Borderline 3; Egypt; rank - |
| diagnostic-saudi-weather: Routine Saudi weather forecasts | Irrelevant; not scored | X (no usable URL); KSA; rank - | Irrelevant 1; KSA; rank - | Irrelevant 1; KSA; rank - | Irrelevant 1; KSA; rank - |
| diagnostic-landscape: Agricultural landscape descriptions | Irrelevant; not scored | X (no usable URL); Unclear; rank - | Borderline 2; Out of Scope/Unclear; rank - | Irrelevant 1; Out of Scope/Unclear; rank - | Borderline 2; Global; rank - |
| diagnostic-economy: Generic economic news mentioning energy | Irrelevant; not scored | X (no usable URL); Unclear; rank - | Borderline 2; Out of Scope/Unclear; rank - | Borderline 2; Out of Scope/Unclear; rank - | Borderline 2; Global; rank - |
| diagnostic-water-science: Water-related laboratory papers without a demonstrated mission application | Borderline; Out of Scope/Unclear, Global | X (no usable URL); Unclear; rank - | Borderline 2; Out of Scope/Unclear; rank - | Borderline 2; Out of Scope/Unclear; rank - | Borderline 2; Global; rank - |
| diagnostic-foreign-water: Foreign-local water infrastructure projects without a MENA or systemic bridge | Irrelevant; not scored | X (no usable URL); Unclear; rank - | Irrelevant 1; Out of Scope/Unclear; rank - | Irrelevant 1; Out of Scope/Unclear; rank - | Irrelevant 1; Out of Scope/Unclear; rank - |

## Reference and model rationales

**rss-00**: Petroleum trade/banking resumption; no supported food, water or transition consequence.

- mini-100: Syria's first letter of credit in 14 years with oil imports via Saudi Aramco signals trade resumption relevant to regional energy and economic stability.
- mini-repartitioned: Syria's letter of credit enabling petroleum imports relates marginally to energy security but unclear if it impacts mission topics strongly.
- nano-100: First Syrian import letter of credit; economic but potential regional water/energy impacts unclear.

**rss-01**: Concrete renewables/export proposal abroad with a Saudi company; credible commercial MENA bridge but foreign project, not KSA geography.

- mini-100: Saudi Acwa and Mongolia cooperation on solar/wind projects with battery storage is a strategic renewable energy initiative relevant to mission.
- mini-repartitioned: Acwa planning solar and wind projects targeting cross-border electricity export affects regional renewable energy transition, thus net zero mission relevant.
- nano-100: Mongolia export projects implicate regional energy trade, relevant but not core.

**rss-02**: Major LNG operational disruption in MENA; indirect transition/security consequences unspecified.

- mini-100: QatarEnergy profit fall due to Iran conflict affects energy exports, a significant systemic development with MENA regional impact.
- mini-repartitioned: QatarEnergy's profit fall from Iran conflict impacts energy exports but unclear direct strategic consequences for mission scope.
- nano-100: Qatar’s LNG issues relate to energy transition; important but indirect.

**rss-03**: Generic industrial IPO investment; no explicit mission application.

- mini-100: Abu Dhabi sovereign fund investment in Indian IPO industrial firm has indirect or uncertain mission relevance.
- mini-repartitioned: Adia's investment in Indian IPO has some commercial interest but no clear mission relevance for Food/Water Security or Net Zero in MENA.
- nano-100: Investments in Zetwerk are economically significant but lack explicit MENA or sustainability link.

**rss-04**: Semiconductor investment without a demonstrated mission application.

- mini-100: GlobalFoundries chip project backed by Abu Dhabi is a tech investment but mission relevance to food/water/net zero MENA unclear.
- mini-repartitioned: GlobalFoundries US-Japan chip project with Abu Dhabi backing impacts tech sector but no direct mission relation for food/water/net zero in MENA.
- nano-100: Semiconductor project in the US with regional implications; relevant but not central.

**rss-05**: Regional logistics support could cover mission supply chains, but sectors unspecified; preserve uncertainty.

- mini-100: Qatar bank grants to help local manufacturers offset soaring shipping costs support industrial food security amid conflict impact.
- mini-repartitioned: Qatar Development Bank grants to offset shipping costs affect industrial and supply chain resilience linked to food and economic security in Gulf.
- nano-100: Qatar grant supports industrial sector; broader economic influence but no direct water/food relation.

**rss-06**: Oil-fleet sanctions/prices without a demonstrated mission consequence.

- mini-100: US easing sanctions on shadow fleet affects oil freight rates and prices; plausible systemic energy impact with uncertain MENA link.
- mini-repartitioned: US easing sanctions on oil shadow fleet affects oil transport and prices, indirectly tied to energy security but mission impact uncertain.
- nano-100: US sanctions easing on shadow fleet; economic but limited direct mission relevance.

**rss-07**: Hydrocarbon export commentary without a supported mission development.

- mini-100: Saudi Oil minister plans alternatives to Hormuz export constraints show strategic energy sector resilience in MENA.
- mini-repartitioned: Saudi plans to convert gas pipeline and reassurances about hydrocarbon supply relate to energy security and operational developments in MENA.
- nano-100: Saudi oil minister’s comments on hydrocarbons reflect supply policy; indirect and general.

**rss-08**: Broad contracts/spending update; energy alone does not establish transition relevance.

- mini-100: Sustained Gulf government spending on energy and transport projects despite war sustains infrastructure and net zero transition relevance.
- mini-repartitioned: Gulf states increasing energy and transport project awards despite war shows strategic infrastructure investment relevant to mission.
- nano-100: Gulf project awards stabilization amid conflict; economic focus.

**rss-09**: Material Hormuz disruption, but cargo/agricultural effects unspecified; potential indirect mission bridge.

- mini-100: Attacks on vessels off Oman near Hormuz choke point impact shipping security essential for regional energy and food supply chains.
- mini-repartitioned: Attacks on vessels near Strait of Hormuz implicate energy transport and global trade routes affecting MENA's strategic stability and supply chains.
- nano-100: Strait of Hormuz attacks increase shipping risks; regional security issue with some indirect relevance.

**oct16-negation**: Trust commentary expressly disclaims energy/water; incidental keywords.

- mini-100: Article about trust and currency future unrelated to food/water/net zero mission topics or MENA impact.
- mini-repartitioned: Article about trust as a currency of the future lacks any explicit or implied connection to food, water security or net zero transition.
- nano-100: Opinion piece on trust, unrelated to mission themes.

**oct16-battery_definition**: Battery definition commentary; no demonstrated practical mission application.

- mini-100: Battery definition general science without direct MENA/systemic mission impact but relevant to net zero technology.
- mini-repartitioned: General battery science with no explicit MENA relevance; systemic global net-zero topic.
- nano-100: Technical discussion of batteries; no MENA or mission relevance.

**oct16-battery_science**: Plausible storage application but no demonstrated deployment; not high relevance.

- mini-100: Advanced battery science research relevant to net zero transition but no stated MENA/systemic application.
- mini-repartitioned: Lithium-ion battery electrolyte science; global net-zero relevance but no MENA specifics.
- nano-100: Scientific battery research with no regional or mission connection.

**oct16-crypto**: Crypto trading license without a mission consequence.

- mini-100: Crypto trading launch unrelated to mission topics or food/water/net zero in MENA.
- mini-repartitioned: Licensed crypto trading in UAE unrelated to food/water security or net-zero transition.
- nano-100: Crypto financial news; no MENA or sustainability focus.

**oct16-flights**: Passenger cancellations without a mission consequence.

- mini-100: Flight disruptions have no clear mission relevance or MENA/systemic food/water/net zero impact.
- mini-repartitioned: Flight disruptions unrelated to mission topics despite MENA geography.
- nano-100: Flight disruptions unrelated to mission themes.

**oct16-commission**: Irrigation awards in France; possible Saudi application but operational consequences unknown. Not a new Saudi project.

- mini-100: Saudi wins international irrigation awards indicating strategic water security achievements in MENA/KSA.
- mini-repartitioned: Saudi Arabia winning international irrigation awards signals leadership in MENA water security infrastructure and policy.
- nano-100: Recognition for irrigation awards in Saudi Arabia; regional impact uncertain but potentially relevant.

**oct16-veal**: New national livestock funding directly supports Egyptian agricultural capacity.

- mini-100: Egypt approving new funding for national veal project supports food security and agricultural investment in Egypt.
- mini-repartitioned: Egypt funding a National Veal Project implicates food security through livestock/agriculture development in Egypt.
- nano-100: Funding for veal project in Egypt; indirect relevance to food system but emphasis on agricultural economy.

**oct16-gerd**: Central Nile water-security topic, but explainer novelty and event geography unresolved.

- mini-100: GERD Nile dam dispute directly concerns Egypt's water security and regional hydropolitics.
- mini-repartitioned: GERD Nile dam dispute directly relates to water security tensions impacting Egypt and MENA.
- nano-100: GERD impacts regional water management, a critical water security issue for Egypt.

**oct16-harvests**: Explicit shipping-to-harvest production consequence; systemic food security.

- mini-100: Hormuz shipping disruption is affecting harvests per UN agency, a consequential food security threat in MENA.
- mini-repartitioned: Hormuz shipping disruption impacting harvests has direct food security consequences in MENA.
- nano-100: Shipping disruptions affecting harvests directly influence food security in MENA region.

**oct16-iraq**: Solar expansion talks in Iraq; Saudi nationality is not project geography.

- mini-100: Iraq talks with Saudi Acwa on solar capacity increase is a strategic renewable energy development with MENA systemic relevance.
- mini-repartitioned: Iraq's talks with Saudi Acwa on solar capacity are net-zero relevant with systemic MENA impact but not country-specific.
- nano-100: Iraq-Saudi solar projects impact regional renewable capacity, relevant to Net Zero transition.

**oct16-libya**: Consequential regional flooding; mission infrastructure/food effects unspecified.

- mini-100: Flood damage in Libya could impact infrastructure; food/water security impact plausible but unclear and outside core MENA.
- mini-repartitioned: Heavy rains causing floods in Libya may affect water infrastructure or agriculture, relevant to water security but lacking detailed mission impact.
- nano-100: Local flooding; possible regional implications but not explicitly mission-critical.

**oct16-qatar**: Potential material renewable share change in other MENA; assess forecast versus funded commitment later.

- mini-100: Qatar's renewable energy share doubling is a major net zero transition development relevant to MENA region.
- mini-repartitioned: Qatar's renewable energy share doubling by 2035 directly relates to net zero transition, relevant to MENA as Qatar is part of GCC region.
- nano-100: Qatar’s renewable energy target directly supports Net Zero goals, significant regional impact.

**oct15-istanbul**: School closures in Turkey without a demonstrated mission infrastructure or food effect.

- mini-100: Heavy rain and flooding in Istanbul may affect food/water security but geography is outside MENA core.
- mini-repartitioned: Flooding in Istanbul may have indirect regional significance but no explicit mission connection or MENA country.
- nano-100: Local weather event unrelated to MENA food or water systems or net zero.

**oct15-hormuz**: Fertilizer-plan failure explicitly threatens food availability; distinct from observed harvest losses.

- mini-100: Failure to activate Hormuz fertilizer plan risks food crisis in MENA; strategic food-security impact in KSA/MENA.
- mini-repartitioned: Failure to activate Hormuz fertilizer plan risks a food crisis in MENA; directly relevant and high mission impact.
- nano-100: Fertilizer plan failure linked to potential food crisis, directly relevant to regional food security.

**oct15-bahrain**: MENA grid investment abroad could enable transition, but technology/purpose absent. Not a Bahrain project.

- mini-100: Bahraini fund investing in power grids in US/Europe lacks clear MENA/systemic mission impact.
- mini-repartitioned: Bahraini fund investment in power grids outside MENA; systemic MENA impact unclear.
- nano-100: Investing in power grids globally; no direct MENA or food/water nexus specified.

**saved-sharjah**: Explicit large water/waste capacity and investment in Sharjah.

- mini-100: Sharjah investments increasing water and waste capacity support vital water security infrastructure for UAE's growth.
- mini-repartitioned: Sharjah's investments in water capacity and waste management infrastructure underpin urban water security and sustainability in UAE.
- nano-100: Water and waste capacity investment in Sharjah; regional relevance uncertain.

**saved-egypt-battery**: Practical lithium-ion assembly capacity development in Egypt.

- mini-100: New lithium-ion battery assembly facility in Egypt supports local renewable energy infrastructure and net zero transition.
- mini-repartitioned: New lithium-ion battery assembly in Egypt supports energy storage infrastructure, key for Egypt's net zero transition goals.
- nano-100: New lithium-ion battery facility in Egypt could impact regional energy tech and supply chains.

**user-west-bank**: Violence against farmers is not proof of food-system disruption; sparse title merits caution, never high relevance from agriculture alone.

- mini-100: West Bank olive farmers facing violence may impact food security locally but uncertain link to systemic mission or MENA regional scale.
- mini-repartitioned: West Bank olive farmers face violence which may impact food production, but scale and systemic food security consequences are unclear.
- nano-100: Conflict-related story with no explicit link to food, water, or net zero themes in MENA.

**diagnostic-uae-strategy**: Potential direct strategic food-capacity relevance; novelty/importance unresolved.

- mini-100: UAE food production strategy is a strategic development in food security within the UAE.
- mini-repartitioned: UAE food-production strategy indicates a direct mission-relevant policy and commercial development in MENA.
- nano-100: UAE food-production strategy directly relates to food security within MENA.

**diagnostic-egypt-green**: Potential industrial transition relevance; no specific new development supplied.

- mini-100: Focus on Egypt’s green industrialization suggests strategic and commercial energy transition development in Egypt, matching mission scope.
- mini-repartitioned: Article about Egypt's green industrialisation suggests strategic development in net-zero transition in a key MENA country.
- nano-100: Focus on green industrialisation in Egypt, potential links to sustainability; importance to regional green growth uncertain.

**diagnostic-saudi-weather**: Ordinary forecast with no demonstrated mission consequence.

- mini-100: Routine weather forecasts provide no demonstrated mission relevance or systemic impact.
- mini-repartitioned: Routine weather forecasts in Saudi Arabia, no mission consequence.
- nano-100: Routine weather forecasts with no clear mission impact on security or sustainability.

**diagnostic-landscape**: Scenery without a mission development.

- mini-100: Generic agricultural landscape descriptions lack clear mission relevance or MENA/systemic context.
- mini-repartitioned: Agricultural landscape descriptions with no clear mission impact or MENA link.
- nano-100: Descriptive on agricultural landscapes; lacks explicit connection to food security or water issues in MENA.

**diagnostic-economy**: Energy keyword alone is insufficient.

- mini-100: Generic economic news mentioning energy lacks specific mission relevance or MENA/systemic bridge, context uncertain.
- mini-repartitioned: Generic economic news mentioning energy without detail, no clear MENA or mission relevance identified.
- nano-100: Mentions energy in general; no clear link to food/water security or net zero within MENA.

**diagnostic-water-science**: Not high relevance; potential application cannot be assessed from this generic description.

- mini-100: Water-related lab papers without demonstrated mission application have uncertain relevance.
- mini-repartitioned: Water-related lab papers without demonstrated mission application; plausibly relevant if further evidence arises.
- nano-100: Laboratory papers lack demonstrated direct mission application or regional impact.

**diagnostic-foreign-water**: Explicitly foreign-local without a regional/systemic link.

- mini-100: Foreign-local water projects without MENA or systemic bridge clearly off mission.
- mini-repartitioned: Foreign-local water infrastructure projects explicitly lacking MENA or systemic bridge; off mission.
- nano-100: Foreign projects without direct MENA impact or systemic bridge, no clear mission relevance.
