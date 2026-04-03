from langchain_core.tools import tool
from tavily import TavilyClient
import os


def _tavily():
    return TavilyClient(api_key=os.environ["TAVILY_API_KEY"])


@tool
def research_trending_topics(query: str) -> str:
    """Research current trending topics, hashtags, and content ideas relevant to a query.
    Use this to find what's trending in the food truck, coffee shop, B2B food supply space.
    Args:
        query: Search query about trends, e.g. 'food truck industry trends 2026' or 'instagram content ideas B2B food supplier'.
    """
    results = _tavily().search(
        query=query,
        search_depth="advanced",
        max_results=5,
    )
    summaries = []
    for r in results.get("results", []):
        summaries.append(f"**{r['title']}**\n{r['content'][:300]}\nSource: {r['url']}")
    return "\n\n---\n\n".join(summaries) if summaries else "No results found."


@tool
def research_competitor_strategies(query: str) -> str:
    """Research what competitors or similar businesses are doing on Instagram.
    Args:
        query: Search query about competitor strategies, e.g. 'food supplier instagram marketing strategy'.
    """
    results = _tavily().search(
        query=f"instagram marketing {query}",
        search_depth="advanced",
        max_results=5,
    )
    summaries = []
    for r in results.get("results", []):
        summaries.append(f"**{r['title']}**\n{r['content'][:300]}\nSource: {r['url']}")
    return "\n\n---\n\n".join(summaries) if summaries else "No results found."


@tool
def find_potential_leads(query: str, location: str = "") -> str:
    """Search for potential B2B leads - food trucks, coffee shops, small restaurants that might need a sandwich supplier.
    Args:
        query: What type of business to find, e.g. 'food trucks looking for suppliers'.
        location: Optional location to narrow the search.
    """
    search_query = f"{query} {location}".strip()
    results = _tavily().search(
        query=search_query,
        search_depth="advanced",
        max_results=10,
    )
    summaries = []
    for r in results.get("results", []):
        summaries.append(f"**{r['title']}**\n{r['content'][:200]}\nURL: {r['url']}")
    return "\n\n---\n\n".join(summaries) if summaries else "No results found."
