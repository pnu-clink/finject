# Viewer-exp record of the family

2026-09-20 • User-defined **The pipeline design is a test run.** I got the emblems from the work.
The next job ID: `01a0b9ae-8110-7a22-bdf3-fb2b7b854c8b`.

## The criteria for this implementation

- The latest customized paths `viewer/experiments`. Previous `exp-viewer/` I'm replacing the proposal.
- The entire theme is brown, referring to the run selection → phrase list → filter → detailed panel structure of the existing data viewer.
- The range of reading of the experimental data is `reports/experiments-run`It doesn't follow the external paths that are written in the production results, the source material, the private.source.
- Six screens: overall results, conditional comparison, case comparison, failure analysis, cost-effectiveness, report-efficiency.
- The screen comparison key is the same running within `case + variant + prompt_condition + reasoning`It doesn't directly connect to different trial_id models.
- The type is the original, the IC-value front/back, the IC source front/back and the IC-relation, the EA-01/02 in this order.
- The text for form failure is also read in the call JSON and the source code. V2, flat V3, V4 answer_meta with the original form.
- The reference right answer is for the analyst, not to reuse it as the right answer to the variation, not to multiply the scale or to extract the numbers and then to tap it.
- The null, the undervalued, the misrepresented cost 0It doesn't convert to success. It doesn's not add in caches, it doesn't add out logical tokens.
- Meaning scores, writeable person captures, automatic integration comparisons between runs, new model calls are not included in this range.

## I've got the current data.

1. [Exit folder and field](../../docs/02-experiments/README.md)
2. [Response agreement](../../docs/02-experiments/README.md)
3. [Local Luna running](../../docs/02-experiments/README.md)
4. [Existence screen design](../../docs/02-experiments/README.md) The previous state of the trajectory is the trajectories.
5. exp-001~004The actual state/summary/plan/public/private/results/calls/analysis file.

The latest completed run exp-004The Luna V4, 3,000The answer is, exp-003The Gemini V2 of both models, 6,000response.
exp-002The expansion of the expansion of001It's an incomplete execution, including the authentication scale.](../../log/viewer-experiments-v1/verification.json)is the location.

## Selection of implementation

And we put the standard library server Node in the same folder, and it doesn't require new dependency installation, and it won't call the existing Python experiment runner or build viewer.
The current implementation of the responsibility, flow, limitations [guide to visualization](../../docs/02-experiments/README.md)And then we follow.
