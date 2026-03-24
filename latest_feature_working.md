You now have a much stronger news automation system. Here is everything you can do right now, with ready-to-use prompt examples.

**Core News File Creation**
1. Create news directly into a file in one step.
Prompt:
Create latest_news.xlsx and fetch top 10 latest news related to US-Iran war in alphabetical order with full story.

2. Works even if your sentence is long or natural-language.
Prompt:
Please create a file latest_news.xlsx and fetch me top 10 latest news related to US-Iran war in latest_news.xlsx in alphabetical order from 1 to 10 with news story.

3. Deterministic planning for news+file prompts.
What this means:
Your plan should reliably choose the right tool and create the target file, instead of random tool choices.

**Supported Output Formats**
1. Excel (.xlsx)
Prompt:
Create sports_news.xlsx and fetch top 15 latest sports news in alphabetical order with story.

2. Text (.txt)
Prompt:
Create entertainment_news.txt with top 10 latest entertainment news in alphabetical order and include story, source, and published time.

3. Word (.docx)
Prompt:
Create world_news.docx and fetch top 12 latest world news in alphabetical order with detailed stories.

4. Markdown (.md)
Prompt:
Create tech_news.md and fetch top 8 latest technology news in alphabetical order with story.

5. JSON (.json)
Prompt:
Create business_news.json and fetch top 20 latest business news with stories.

6. CSV (.csv)
Prompt:
Create health_news.csv and fetch top 10 latest health news in alphabetical order.

**Topic Coverage (Now Broader)**
1. Conflict/geopolitics
Prompt:
Create iran_conflict_news.xlsx with top 10 latest US-Iran conflict news in alphabetical order.

2. Sports
Prompt:
Create sports_news.docx and fetch top 10 latest sports news in alphabetical order with story.

3. Entertainment
Prompt:
Create entertainment_news.txt and fetch top 10 latest entertainment news in alphabetical order.

4. Business
Prompt:
Create market_news.xlsx and fetch top 10 latest business and market news in alphabetical order.

5. Technology
Prompt:
Create ai_news.md and fetch top 10 latest AI and technology news in alphabetical order.

6. Health
Prompt:
Create health_news.json and fetch top 10 latest health news in alphabetical order.

**Story Quality Improvements**
1. Story enrichment mode is active by default.
What this means:
If RSS gives only short/weak text, system tries to pull fuller article context.

2. Better fallback behavior.
What this means:
If full extraction is not possible, it gives a clear fallback story instead of just repeating headline text.

3. You can still ask explicitly for richer output.
Prompt:
Create latest_news.xlsx and fetch top 10 latest US-Iran news with expanded story text, not just headline summary.

**Sorting and Ranking**
1. Alphabetical sorting by headline supported.
Prompt:
Create latest_news.xlsx with top 10 latest US-Iran news sorted alphabetically by headline.

2. Ranked output from 1..N included.
Prompt:
Create latest_news.docx with top 10 latest sports news in alphabetical order with rank numbers 1 to 10.

**Reliability Improvements You Can Benefit From**
1. Better endpoint behavior for plan + execution flow.
What this means:
If a step fails, execution status now reflects failure properly instead of false success.

2. Better error handling from tools.
What this means:
Tool-level errors are now surfaced correctly during execution.

3. Better file path parsing from prompts.
What this means:
Prompts like “create a file latest_news.xlsx and fetch…” now correctly use latest_news.xlsx as output path.

**Multi-Format Universal Prompt Pattern**
Use this pattern for almost anything:
Create <file_name>.<format> and fetch top <N> latest <topic> news in alphabetical order with story.

Examples:
1. Create football_news.txt and fetch top 25 latest football news in alphabetical order with story.
2. Create celebrity_news.docx and fetch top 10 latest entertainment news in alphabetical order with story.
3. Create startup_news.json and fetch top 30 latest startup and technology news in alphabetical order with story.

**Practical Notes**
1. Files are created inside sandbox workspace.
2. If a source has fewer relevant items, output may contain fewer rows and report shortage.
3. Some feeds may intermittently fail, but others still populate output when available.

If you want, I can also give you a ready-made “prompt pack” of 25 high-quality prompts (grouped by topic + format) you can copy-paste directly.