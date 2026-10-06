# Model bake-off (free tier)

Same prompt, same strict JSON schema, same cases. Replies are recorded once (`evals/cassettes/`) and scored offline.

| Model | Held-out: LLM alone | Held-out: in the cascade | Red-team: model alone fails | Red-team: full pipeline fails | Tokens / call | Median latency |
|---|---|---|---|---|---|---|
| `openai/gpt-oss-20b` | 32/48 (67%) | 44/48 (92%) | 14/76 (18%) | 0/76 (0%) | n/a | n/a |
| `openai/gpt-oss-120b` | 35/48 (73%) | 44/48 (92%) | 17/92 (18%) | 0/92 (0%) | 1139 (n=143) | 1077 ms |
| `qwen/qwen3.8-27b` | 40/48 (83%) | 45/48 (94%) | 16/93 (17%) | 0/93 (0%) | 435 (n=144) | 500 ms |

Each column counts only the messages that model has a recorded reply for; the denominators say how many.

## Reading it

- **The model changes accuracy and cost, not safety.** Alone, every model drops or overrides a stated diet, allergen or budget on roughly one in six hostile or awkward messages; behind the deterministic reader and the merge rules, none does. Choosing a model is a cost, latency and recall decision, which is what the design intended.
- **Accuracy:** the smaller `qwen/qwen3.8-27b` reads held-out messages better than either gpt-oss model when used alone.
- **Cost:** it also uses about 40% of the tokens per call (the free tier is 8,000 tokens/minute and 200,000/day per model), so the same quota covers roughly 2.5x as many customers, and it answers in about half the time.
- **Caveats:** one run per model at temperature 0, 48 held-out cases, so differences of a few points are noise. The prompt was written and tuned on gpt-oss-20b, which if anything favours it. Tokens and latency for gpt-oss-20b are n/a because its replies were recorded before the harness captured them (earlier measurements put it near 1,100 tokens per call). Model availability on the free tier changes; re-record to refresh.

