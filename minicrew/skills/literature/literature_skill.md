# literature skills

Literature — web retrieval

_Auto-generated (`minicrew skills --write`). Skills are defined in `src/minicrew/core/skills_impl.py`; standalone processing scripts live in this folder._

### `literature_search`
Search the web literature (Semantic Scholar or OpenAlex — open APIs, no key) for papers on a topic: returns title, authors, year, venue, DOI, citation count, abstract, and URL. Use to find external evidence / precedents; pair with `distill` to store a vetted note. Abstracts only (not full text); verify claims against the source before trusting.
- **requires:** network
- **args:**
  - `query` (string, required) — search query (keywords/phrase)
  - `limit` (number, optional) — max papers (default 8)
  - `source` (string, optional) — openalex (default) | semantic_scholar
  - `year_from` (number, optional) — optional earliest year
