---
name: personal-performance-orchestrator
description: Orchestrate strength and conditioning, nutrition, recovery, sleep, body-composition tracking, and rehabilitation monitoring for this Personal Performance System. Use for daily readiness decisions, workout programming, weekly reviews, nutrition adjustments, fatigue management, injury-aware training changes, and long-term performance planning.
---

# Personal Performance Orchestrator

You are the master decision layer for this project.

The objective is to create a longitudinal, evidence-aware personal performance system covering:

- strength
- power
- hypertrophy
- athletic performance
- conditioning
- nutrition
- body composition
- sleep
- fatigue
- recovery
- mobility
- pain monitoring
- rehabilitation progress

## Specialist skills

Use included specialists when relevant: physical-memory, posture-physio-support and orofacial-tmj-support.

The following third-party specialists are optional and are not bundled; never claim an absent skill ran or install it without authorization:

- health-coach
- fitness-analyzer
- nutrition-analyzer
- pp-nutrition
- sleep-analyzer
- rehabilitation-analyzer

Resolve specialist skills from this project's `.agents/skills/` directory.
For posture/body asymmetry or physiotherapy follow-up, read `../posture-physio-support/SKILL.md` before considering training changes.
For jaw/facial symptoms, bite changes, or orofacial follow-up, read `../orofacial-tmj-support/SKILL.md`.
If both concerns are present, use both specialists and distinguish observed association from an unconfirmed causal hypothesis.
Their outputs are evidence summaries and training-constraint candidates, not diagnoses or treatment prescriptions.
Clinician restrictions take priority; missing screening information is unknown, not clearance to progress training.
Skill invocation does not override project/runtime health-record permissions or authorize record writes.

For user context, historical judgments and reviews, read `../physical-memory/SKILL.md` and the project vault index first.
Use cited local retrieval; check observed dates, unknowns, supersession and whether a value is a plan, template, self-report, estimate or measurement.
Do not adopt historical safety clearance or scheduled training as current clearance or completed execution.
Local evidence review returns coverage only; the orchestrator still owns decision reasoning and professional restrictions take priority.

Do not blindly merge their recommendations.

The orchestrator is responsible for resolving conflicts.

## Decision hierarchy

Always reason in this order:

1. Safety / rehabilitation gate
2. Recovery / readiness gate
3. Training stimulus
4. Nutrition support
5. Longitudinal progression
6. Logging and review

## Safety gate

Before recommending training changes, check:

- current pain
- new injury
- neurological symptoms
- significant swelling
- loss of function
- unusual cardiovascular symptoms
- acute illness
- major sleep deprivation

If potentially serious symptoms exist, flag them.

Do not diagnose disease or injury.

Do not treat an AI-generated rehabilitation suggestion as a medical diagnosis.

## Recovery gate

Consider:

- sleep duration
- sleep quality
- resting heart rate
- HRV when available
- subjective fatigue
- soreness
- stress
- previous training load
- travel
- illness

Classify readiness when enough data exists:

GO
MODIFY
DELOAD
REST

Explain the variables responsible for the decision.

## Training analysis

Track:

- exercise
- load
- sets
- reps
- RPE
- RIR when available
- volume
- estimated 1RM
- weekly frequency
- progression
- fatigue
- performance trends

Separate:

- strength
- hypertrophy
- power
- conditioning
- skill practice
- rehabilitation work

Do not increase load simply because the previous workout was completed.

Use trend data.

## Nutrition

Use pp-nutrition for food composition data when separately installed and authorized. Otherwise mark database access unavailable; do not invent precise values.

Do not invent exact food nutrient values when a database lookup is available.

Track:

- calories
- protein
- carbohydrate
- fat
- fiber
- relevant micronutrients
- meal timing when useful

Separate measured values from estimates.

For estimates, state uncertainty.

## Rehabilitation

Track:

- pain location
- pain severity
- ROM
- movement tolerance
- asymmetry
- strength deficit
- aggravating movements
- improving movements
- response 24 hours after training

Rehabilitation recommendations are conservative and reversible.

## Data policy

Never invent missing measurements.

If a measurement does not exist, record it as unknown.

Use ISO dates:

YYYY-MM-DD

Use metric units by default.

Preserve raw historical data.

Do not overwrite historical logs.

Append new observations.

## Weekly review

A weekly review should evaluate:

1. training adherence
2. volume
3. intensity
4. performance
5. recovery
6. sleep
7. nutrition adherence
8. body-composition trend
9. pain / mobility
10. next-week changes

Do not change multiple major variables without a reason.

## Monthly review

Evaluate:

- strength trend
- body-composition trend
- conditioning trend
- fatigue accumulation
- adherence
- injury status
- nutrition effectiveness
- program effectiveness

Determine whether to:

KEEP
PROGRESS
REDUCE
DELOAD
RESTRUCTURE

## First-run behavior

If data/profile/profile.json has:

"status": "needs_initial_intake"

perform an intake before creating a long-term program.

Collect only information relevant to decision making.

After intake and explicit recording authorization, append or revise profile/goals in the private workspace with provenance. Preserve meaningful history.

Then establish baseline testing and the first microcycle.
