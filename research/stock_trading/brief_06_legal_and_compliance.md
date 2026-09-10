# Research Brief 06: Legal & Compliance
## Paste this entire brief into Perplexity / Gemini Deep Research / Claude

---

## CONTEXT
I'm building "AlphaHound" — a stock sentiment intelligence platform that scrapes Reddit, X/Twitter, news sites, and SEC filings to generate trading signals. I plan to sell this as a SaaS product (API + dashboard) to retail traders, eventually expanding to institutional clients.

I need to understand the legal landscape BEFORE I build, not after. I'm based in the US and the platform will be hosted on Azure.

## WHAT I NEED

### Part 1: Data Collection Legality
1. **Reddit:** After the 2023 API pricing changes and the Reddit IPO, what are the legal restrictions on commercial use of Reddit data? Can I sell products derived from Reddit sentiment analysis? What does their current ToS say?
2. **X/Twitter:** Same question. After Elon's API changes, what are the commercial use rights at each API tier? Can I resell insights derived from X data?
3. **News scraping:** What's the legal status of scraping CNBC, Bloomberg, Reuters for headlines? Fair use? Do I need licensing agreements?
4. **SEC EDGAR:** This is public data — any restrictions on commercial use of EDGAR filings?
5. **StockTwits:** API ToS for commercial use?

### Part 2: Financial Signal Regulations
1. **Do I need SEC registration to sell AI-generated trading signals?** (Investment advisor registration? Broker-dealer?)
2. **What disclaimers are legally required?** ("Not financial advice" — does that actually protect you?)
3. **Am I liable if someone loses money following AlphaHound signals?**
4. **What's the difference between selling "data" vs selling "advice"?** (Selling sentiment scores = data? Selling "BUY STNG" = advice?)
5. **Do I need a Series 65 or Series 66 license?**
6. **What about the Investment Advisers Act of 1940?** Does it apply to algorithmic signal providers?

### Part 3: Precedents & Case Law
1. **Has any AI/algorithmic trading signal company been sued or fined by the SEC?** What happened?
2. **How do competitors handle legal compliance?** (What disclaimers does LunarCrush, StockTwits, Unusual Whales use?)
3. **Are there any safe harbor provisions for algorithmic signal providers?**

### Part 4: Data Privacy
1. **GDPR implications** if European users access the platform
2. **CCPA implications** for California users
3. **Data retention requirements** for financial signal providers
4. **User data handling** — what can I collect, store, and share?

## OUTPUT FORMAT
Start with a clear YES/NO assessment of "can I legally build and sell this?" Then detail the specific requirements, licenses, and disclaimers needed. Include specific examples of how competitors handle compliance.

---
*Save the response as: `legal_compliance_results.md` in this folder*
