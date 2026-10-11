# Project-local skills

The public toolkit includes four independently authored skills:

| Skill | Scope |
| --- | --- |
| personal-performance-orchestrator | Coordinate evidence, recovery, training and follow-up decisions |
| physical-memory | Record, import, compile, retrieve and review local evidence |
| posture-physio-support | Describe posture/function concerns and prepare physiotherapy follow-up |
| orofacial-tmj-support | Track jaw/orofacial symptoms and prepare professional follow-up |

They live in `.agents/skills/` and are never installed globally by this project.
Your agent host must support or explicitly read project-local `SKILL.md` files.
Without an agent host, the Python memory CLI still runs independently.

Optional third-party specialists used by some private deployments are not
bundled. Check each upstream license, scope and permissions before installing
an explicitly selected skill into your own project-local pool:

- [agentic-awesome-skills](https://github.com/sickn33/agentic-awesome-skills): fitness, nutrition, sleep and rehabilitation analyzers.
- [health-coach](https://github.com/H1an1/health-coach): health logging and coaching.
- [printing-press-library](https://github.com/mvanhorn/printing-press-library): nutrition-related reference skills.

A missing optional skill must be reported as unavailable. Do not claim it ran,
fetch it automatically or invent its findings. Upstream code/skills are not
medical evidence; follow the host's research workflow when current clinical
guidance is needed.
