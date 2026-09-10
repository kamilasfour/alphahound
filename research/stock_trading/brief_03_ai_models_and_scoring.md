# Research Brief 03: AI Models & Sentiment Scoring
## Paste this entire brief into Perplexity / Gemini Deep Research / Claude

---

## CONTEXT
I'm building "AlphaHound" — a stock sentiment platform that combines fast quantitative sentiment scoring (FinBERT-style) with slow qualitative narrative reasoning (LLM-style). The platform processes ~100K social media posts and news articles per day across 500+ tickers, scoring each for sentiment, detecting emerging narratives, and flagging divergence between retail and institutional positioning.

I'm building on Azure with Python/FastAPI, PostgreSQL/TimescaleDB, and I'll use the Claude API for the reasoning layer. I need to understand the AI/ML landscape for financial sentiment analysis to make the right architecture decisions.

## WHAT I NEED

### Part 1: Model Comparison
Compare these models/approaches for financial sentiment scoring:

| Model | Type | Training Data | Accuracy on Financial Text | Speed | Cost | Best For |
|-------|------|--------------|--------------------------|-------|------|----------|
| FinBERT | Fine-tuned BERT | Financial news | ? | ? | ? | ? |
| FinGPT | Open-source financial LLM | Diverse financial | ? | ? | ? | ? |
| BloombergGPT | Proprietary | Bloomberg data | ? | ? | ? | ? |
| VADER | Rule-based | General | ? | ? | ? | ? |
| TextBlob | Rule-based | General | ? | ? | ? | ? |
| Claude API | General LLM | Broad training | ? | ? | ? | ? |
| GPT-4 API | General LLM | Broad training | ? | ? | ? | ? |
| RoBERTa (fine-tuned) | Fine-tuned transformer | Custom | ? | ? | ? | ? |
| XLNet (financial) | Transformer | Custom | ? | ? | ? | ? |

For each model, I need:
1. **Published accuracy** on financial NLP benchmarks (PhraseBank, FiQA, SemEval)
2. **Performance on Reddit-style text** (short, sarcastic, emoji-heavy, slang like "diamond hands," "ape," "HODL")
3. **Inference speed** (posts per second on a single GPU vs CPU)
4. **Self-hosting cost** (GPU requirements, memory, Azure VM sizing)
5. **API cost** (if cloud-hosted, cost per 1,000 classifications)
6. **Fine-tuning feasibility** (can I fine-tune on my own labeled data? effort required?)

### Part 2: Architecture Decision
I'm considering a two-tier architecture:
- **Tier 1 (Fast):** FinBERT or similar for bulk scoring every post (bullish/bearish/neutral + confidence score). Runs on every single post, 100K/day.
- **Tier 2 (Deep):** Claude API for narrative reasoning — only runs on aggregated data or when divergence is detected. Maybe 100-500 calls/day.

Questions:
1. Is this two-tier approach the industry standard? Who else does this?
2. What's the optimal split between fast scoring and deep reasoning?
3. How do you handle FinBERT's weakness with sarcasm/irony? Pre-processing filters? Ensemble with a sarcasm detector?
4. What's the accuracy improvement of FinBERT + LLM ensemble vs FinBERT alone?

### Part 3: Sarcasm & Noise Handling
Reddit and X are FULL of sarcasm, irony, and coded language ("to the moon 🚀", "rug pull incoming", "this is financial advice" = ironic). How do the best systems handle this?

1. What sarcasm detection models exist for financial text?
2. Is volume of mentions more reliable than sentiment polarity for prediction? (Research evidence)
3. How do you filter bot accounts, pump-and-dump spam, and coordinated manipulation?
4. What's the false positive rate of sentiment models on Reddit text?

### Part 4: The Scoring Engine Design
I want to output a signal score (1-10) and confidence score (1-10) per ticker. Help me design the scoring methodology:

1. What inputs should feed the score? (sentiment polarity, volume, velocity, source reliability, institutional alignment, technical alignment, historical pattern match)
2. How should inputs be weighted? (Is there academic research on optimal weighting?)
3. How do you calibrate confidence? (What makes a 9/10 confidence vs 4/10?)
4. How do you handle conflicting signals? (Reddit bullish, institutions selling, price falling — what's the right output?)
5. What's the minimum number of data points needed for a reliable score per ticker?

## WHAT I SPECIFICALLY WANT TO KNOW
1. **If I could only pick ONE model for the fast scoring layer, which one and why?**
2. **What's the realistic accuracy ceiling for social media sentiment → stock price prediction?** (Academic consensus)
3. **How much does fine-tuning FinBERT on Reddit financial text improve accuracy?** (Any published results?)
4. **What's the compute cost to score 100K posts/day with FinBERT on Azure?** (VM size, GPU requirements, monthly cost)
5. **Has anyone published results from combining FinBERT + LLM reasoning?** What was the improvement?

## OUTPUT FORMAT
Start with a recommendation (what to build), then the detailed comparison tables, then the scoring engine design. Be opinionated — tell me what to do, not just what exists.

---
*Save the response as: `ai_models_results.md` in this folder*
