from langgraph.prebuilt import create_react_agent
from config import get_llm

from tools.research import find_potential_leads, research_trending_topics
from tools.db_tools import db_get_leads, db_add_lead, db_update_lead

SYSTEM_PROMPT = """You are the Lead Generator for Capa & Co, a B2B sandwich supplier
serving food trucks and small coffee places.

YOUR TASK: Find potential B2B customers who could buy sandwiches from Capa & Co.

PROCESS:
1. Check existing leads to avoid duplicates (db_get_leads)
2. Search for potential new leads (find_potential_leads)
3. For each promising lead, add them to the database (db_add_lead)
4. For existing leads that need updating, use db_update_lead

TARGET CUSTOMERS:
- Food trucks (especially those serving lunch crowds)
- Small coffee shops that want to add food to their menu
- Catering companies looking for sandwich suppliers
- Small restaurants that outsource sandwich prep

SEARCH STRATEGIES:
- Search for food trucks in specific areas
- Look for coffee shops expanding their menu
- Find catering companies seeking suppliers
- Search for new food truck businesses launching

For each lead, capture: business_name, business_type, source, and any available
instagram_handle, location, follower_count. Add notes about why they're a good prospect.

QUALITY OVER QUANTITY: Better to find 3-5 strong leads than 20 weak ones.
"""


def create_lead_generator():
    llm = get_llm(temperature=0.5)

    tools = [
        find_potential_leads,
        research_trending_topics,
        db_get_leads,
        db_add_lead,
        db_update_lead,
    ]

    return create_react_agent(model=llm, tools=tools, prompt=SYSTEM_PROMPT)
