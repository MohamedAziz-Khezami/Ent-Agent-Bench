# Which task types this tier draws from. Everything else about a task
# (action count, distractors, phrasings) lives INSIDE the template file:
# templates/easy/<name>.yaml — each tier owns self-contained copies.
TIER_CONFIG = {
    "templates": ["act_on_a_deal", "act_on_a_followup", "count_open_deals"],
}
