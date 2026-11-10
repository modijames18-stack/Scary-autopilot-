"""Resilient entry point for Scary Autopilot.

Uses the existing production pipeline, but provides a local story-writing fallback
when Gemini/Claude is unavailable or over quota. No API key is required for the
fallback. Video rendering and Edge TTS still need the runner's normal dependencies
and network access. Publishing still requires valid platform credentials.
"""
import json
import random
import re

import autopilot as app


def _make_story(fmt):
    """Create a locally generated, evidence-aware future-risk explainer."""
    topics = [
        ("Will AI Take Your Job?", "AI and employment", "AI can already automate parts of writing, analysis, customer service and repetitive office work. That does not mean every job will disappear. Some tasks may change, some roles may shrink, and new work may emerge. The outcome depends on adoption, costs, regulation, education and how the benefits are shared."),
        ("What If the Internet Went Dark?", "a global internet outage", "The internet is made of many networks, cables, data centres, satellites and power systems. A worldwide outage is an extreme hypothetical, not an expected single switch being turned off. Large disruptions could still affect payments, communication, transport, hospitals and supply chains."),
        ("What Happens When Rivers Run Dry?", "water scarcity", "Drought, overuse, pollution, warming and poor water management can reduce river flows. The effects can reach farms, electricity, wildlife and drinking-water supplies. The severity varies by basin, season and local decisions."),
        ("Why Can a River Turn Red?", "red rivers", "Water can look red or rust-coloured because of iron-rich minerals, certain algae, sediment or pollution. The colour alone does not identify the cause, and it is not evidence that water has become blood. Testing by environmental authorities is essential."),
        ("Could One Government Rule the World?", "global political power", "A single world government is a political thought experiment, not an established secret plan. It raises difficult questions about representation, national sovereignty, accountability, minority rights and how power could be limited."),
        ("What If Earth Crossed a Climate Tipping Point?", "climate and ecosystems", "Climate change increases risks such as heat extremes, heavier rainfall in some regions, drought in others, sea-level rise and ecosystem stress. Specific outcomes depend on emissions, geography, adaptation and policy."),
        ("Can Humanity Control Its Own Technology?", "powerful future technologies", "New technologies can improve medicine, science and productivity while creating risks involving safety, privacy, cyber security, inequality and concentrated power. Good oversight and public participation matter."),
    ]
    title, topic, facts = random.choice(topics)
    if fmt == "short":
        narration = (
            f"Imagine this: {topic} changes your life tomorrow. What is actually possible, and what is just fear? "
            f"{facts} The important question is not only what could go wrong. It is what we can do now. "
            "Governments can plan, scientists can monitor risks, businesses can act responsibly, and communities "
            "can protect vulnerable people. Individuals can learn, prepare sensibly and demand transparent decisions. "
            "This is a scenario to examine, not a prediction. What solution would make the biggest difference where you live?"
        )
    else:
        sections = [
            f"Start with a question: what would happen if {topic} became one of the defining challenges of our generation? It is an unsettling possibility, but a useful one to examine carefully. The purpose of this documentary is not to announce that disaster is coming. It is to understand the mechanisms, the warning signs and the choices that could reduce harm.",
            facts + " These details matter because dramatic headlines can hide important differences between a local event, a regional problem and a global crisis. Good analysis asks where the evidence comes from, how strong it is and what remains uncertain.",
            "There are usually several forces at work. Technology, economics, public policy, geography and human behaviour interact. A problem may grow when institutions ignore early warnings, when information is unreliable, or when the costs fall on people with the fewest resources. It can become less severe when communities share information, invest in resilient systems and make decisions before an emergency.",
            "For ordinary people, the consequences are practical. Families may face higher costs, interrupted services, changing work, health risks or pressure to move. Small businesses and farmers may have fewer resources to adapt. Hospitals, schools and local authorities may need backup plans. The impact will not be identical everywhere, which is why local evidence and community knowledge are essential.",
            "It is also important to challenge easy answers. No single invention, law or leader can solve every complex risk. Some proposed solutions create new problems if they are rushed or imposed without public oversight. Decisions should be transparent, based on evidence, open to scrutiny and designed to protect people who are most exposed.",
            "What can be done? First, measure the problem honestly and publish reliable information. Second, invest in prevention and resilient infrastructure. Third, educate people and make practical plans before a crisis. Fourth, support research and independent oversight. Finally, include workers, residents, scientists and affected communities in decisions rather than leaving the future to a small group.",
            "The future is not fixed. A risk is not a prophecy. The choices made by governments, companies and ordinary people can change what happens next. The most useful question is not simply whether we should be afraid. It is what evidence we need, what safeguards are missing and which solutions we can begin today. What would you change first?"
        ]
        narration = "\n\n".join(sections)
    return {
        "title": title,
        "description": f"A balanced, thought-provoking explainer about {topic}. It separates established facts from uncertainty and explores practical solutions.",
        "tags": ["future", "science", "technology", "documentary", "solutions", "education"],
        "narration": narration,
        "visual_keywords": [
            "documentary footage about " + topic,
            "scientists researching " + topic,
            "ordinary people affected by " + topic,
            "infrastructure related to " + topic,
            "newsroom research and data analysis",
            "community planning and public discussion",
            "practical solutions and resilient technology",
            "earth from space documentary footage",
        ],
    }


def _local_ai(system, prompt, max_tokens=4000, json_mode=False):
    # write_script and its optional polish pass both request the same JSON shape.
    if "Reply with ONLY a JSON object" in prompt or "Improve this short documentary script" in prompt:
        fmt = "short" if "SHORT vertical explainer" in prompt or "short documentary script" in prompt else "long"
        return json.dumps(_make_story(fmt), ensure_ascii=False)
    return "Use a gripping question, explain one future risk with evidence and uncertainty, show human impacts, and end with practical solutions."


def _local_research(fmt, hist):
    return (
        "Local fallback: use an immediate curiosity hook, a specific unsettling setting, "
        "short spoken sentences, escalating clues, atmospheric visuals, and a final reveal. "
        "Create an original plot; do not imitate existing videos."
    )


# Prefer the configured AI provider. If it times out, is over quota, or is
# unavailable, fall back to local original-story generation so a run can continue.
_network_ai = app.ask_ai
_network_research = app.research

def _resilient_ai(system, prompt, max_tokens=4000, json_mode=False):
    try:
        return _network_ai(system, prompt, max_tokens=max_tokens, json_mode=json_mode)
    except Exception as exc:
        print("AI provider unavailable; using local story fallback:", str(exc)[:300])
        return _local_ai(system, prompt, max_tokens=max_tokens, json_mode=json_mode)

def _resilient_research(fmt, hist):
    try:
        return _network_research(fmt, hist)
    except Exception as exc:
        print("Research unavailable; using local guidance:", str(exc)[:300])
        return _local_research(fmt, hist)

app.ask_ai = _resilient_ai
app.research = _resilient_research

if __name__ == "__main__":
    app.main()
