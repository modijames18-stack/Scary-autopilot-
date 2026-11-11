"""Curated, authoritative evidence references for Scary Autopilot.

The summaries below are research prompts, not a substitute for reading the linked
reports. Scripts must preserve uncertainty and must not claim a source proves more
than its listed support statement.
"""

TOPICS = {
    "AI and jobs": {
        "evidence": [
            "ILO's 2026 review says measured productivity gains from generative AI are real but uneven; large-scale job displacement remains limited in the evidence reviewed so far. Risks include inequality, fewer opportunities for younger workers, and changes to job quality and worker autonomy.",
            "The ILO's 2025 update estimates one in four workers worldwide are in occupations with some degree of generative-AI exposure, while most jobs are more likely to be transformed than made redundant because human input remains necessary."
        ],
        "sources": [
            {
                "title": "The impact of GenAI on jobs, productivity and work organization: a review of the empirical evidence",
                "url": "https://www.ilo.org/publications/impact-genai-jobs-productivity-and-work-organization-review-empirical",
                "supports": "The empirical evidence reviewed by the ILO on productivity, job displacement, inequality, youth employment opportunities, and work organization."
            },
            {
                "title": "Generative AI and jobs: A 2025 update",
                "url": "https://www.ilo.org/publications/generative-ai-and-jobs-2025-update",
                "supports": "The ILO's estimates of occupational exposure to generative AI and its finding that job transformation is more likely than wholesale redundancy for most occupations."
            }
        ]
    },
    "Global AI governance and concentration of power": {
        "evidence": [
            "The UN's Independent International Scientific Panel on AI describes opportunities and risks across economic, social, security, environmental, human-rights, and governance domains, and warns that safeguards may not be keeping pace with AI capabilities.",
            "The UN's Global Digital Compact and AI governance dialogue are real international cooperation mechanisms. They do not establish a one-world government; any scenario about a single world authority must be explicitly presented as hypothetical."
        ],
        "sources": [
            {
                "title": "Preliminary Report of the Independent International Scientific Panel on AI",
                "url": "https://www.un.org/independent-international-scientific-panel-ai/en/preliminary-report",
                "supports": "The UN panel's evidence-based assessment of AI capabilities, opportunities, risks, and governance challenges."
            },
            {
                "title": "Artificial Intelligence (AI)",
                "url": "https://www.un.org/en/global-issues/artificial-intelligence",
                "supports": "The UN's description of existing international AI-governance cooperation, the Global Digital Compact, and the scientific panel."
            },
            {
                "title": "UN Global Risk Report 2026",
                "url": "https://www.un.org/global-risk-report",
                "supports": "The 2026 UN stakeholder survey's reported perceptions of global risks, including AI and concentration of power; perceptions are not predictions."
            }
        ]
    },
    "Water scarcity and drying rivers": {
        "evidence": [
            "UN-Water reports that water scarcity connects health, food security, ecosystems, and climate resilience, and that water stress is already substantial in several regions.",
            "The 2026 UN World Water Development Report highlights unequal access to safely managed drinking water and the effects of climate change, water scarcity, and disasters on people and livelihoods.",
            "A 2026 UN University report describes severe stress in some river basins and aquifers from overuse, pollution, land degradation, and climate pressures; the condition varies by basin and should not be generalized to every river."
        ],
        "sources": [
            {
                "title": "Water Scarcity",
                "url": "https://www.unwater.org/water-facts/water-scarcity",
                "supports": "UN-Water facts and figures on global water stress, agricultural water scarcity, drought impacts, and water withdrawals."
            },
            {
                "title": "UN World Water Development Report 2026",
                "url": "https://www.unwater.org/publications/un-world-water-development-report-2026",
                "supports": "The 2026 UN assessment of water access, inequality, water scarcity, climate pressures, and impacts on livelihoods."
            },
            {
                "title": "UNU-INWEH report on Global Water Bankruptcy",
                "url": "https://www.unwater.org/news/unu-inweh-report-global-water-bankruptcy",
                "supports": "The UN University assessment of overused river basins and aquifers, groundwater depletion, pollution, and water-system stress."
            }
        ]
    },
    "Power-grid resilience and worldwide blackout scenarios": {
        "evidence": [
            "The IEA describes power-system resilience as the ability to withstand shocks and restore service. Threats vary by country and include severe weather, geopolitical disruption, cyberattacks, infrastructure failures, and planning weaknesses.",
            "A worldwide simultaneous blackout is a hypothetical scenario, not an established forecast. A responsible investigation should explain interconnected risks, local grid differences, backup systems, and recovery measures."
        ],
        "sources": [
            {
                "title": "Energy System Resilience",
                "url": "https://www.iea.org/reports/energy-system-resilience/executive-summary",
                "supports": "The IEA's explanation of energy-system resilience, disruption risks, preparation, and restoration."
            },
            {
                "title": "Analytical frameworks for electricity security",
                "url": "https://www.iea.org/reports/analytical-frameworks-for-electricity-security",
                "supports": "The IEA's definitions of electricity security, adequacy, operational security, and resilience."
            },
            {
                "title": "Electricity 2026: Executive summary",
                "url": "https://www.iea.org/reports/electricity-2026/executive-summary",
                "supports": "The IEA's analysis of grid expansion, flexibility, demand growth, data centres, and electricity-system pressures."
            }
        ]
    },
    "Internet infrastructure and global connectivity": {
        "evidence": [
            "International connectivity depends heavily on submarine telecommunications cables. The ITU describes physical damage, repair delays, geographic concentration, and dependence on a limited number of cable systems as resilience challenges.",
            "A global internet outage is a hypothetical scenario. Real incidents can be regional or service-specific; documentaries must distinguish cable failures, satellite disruptions, cyber incidents, power failures, and platform outages."
        ],
        "sources": [
            {
                "title": "International Advisory Body approves landmark report to strengthen submarine cable resilience",
                "url": "https://www.itu.int/en/mediacentre/Pages/PR-2026-07-10-Submarine-cable-resilience-report.aspx",
                "supports": "The ITU's 2026 description of submarine-cable importance and resilience risks, including physical exposure, repair delays, and geographic concentration."
            },
            {
                "title": "Global Connectivity Report 2025",
                "url": "https://www.itu.int/itu-d/reports/statistics/global-connectivity-report-2025/",
                "supports": "The ITU's assessment of global internet connectivity, access gaps, and the role of submarine cables and satellites."
            },
            {
                "title": "Submarine Cable Resilience",
                "url": "https://www.itu.int/digital-resilience/submarine-cables/",
                "supports": "The ITU's overview of submarine cable dependence, reported cable faults, and international resilience measures."
            }
        ]
    },
    "Climate change, extreme weather and food security": {
        "evidence": [
            "The IPCC reports that climate change has already caused substantial impacts on ecosystems, water security, and food security, with vulnerability and impacts differing across regions.",
            "The IPCC assesses observed increases in several types of weather and climate extremes, including heat extremes, heavy precipitation, drought, and fire weather. Attribution and confidence differ by event type and region."
        ],
        "sources": [
            {
                "title": "AR6 Synthesis Report: Summary for Policymakers",
                "url": "https://www.ipcc.ch/report/ar6/syr/summary-for-policymakers/",
                "supports": "The IPCC's synthesis of observed climate impacts, vulnerability, water security, and food security."
            },
            {
                "title": "Climate Change 2022: Impacts, Adaptation and Vulnerability — Summary for Policymakers",
                "url": "https://www.ipcc.ch/report/ar6/wg2/chapter/summary-for-policymakers/",
                "supports": "The IPCC's assessment of climate-related impacts, adaptation, drought, floods, heatwaves, and food-system risks."
            },
            {
                "title": "Climate Change 2021: The Physical Science Basis — Chapter 11",
                "url": "https://www.ipcc.ch/report/ar6/wg1/chapter/chapter-11/",
                "supports": "The IPCC's assessment of weather and climate extremes, including different types of drought and their regional patterns."
            }
        ]
    },
    "Red or discolored rivers and harmful algal blooms": {
        "evidence": [
            "Water can appear red or otherwise discolored for several different reasons. Some harmful algal blooms can produce red, brown, green, or blue discoloration, but not all blooms are red and not all algal blooms are harmful.",
            "Nutrient runoff, warm temperatures, low flows, and stagnant conditions can contribute to some freshwater harmful algal blooms. A red river should never be described as blood or treated as proof of a single cause without local testing."
        ],
        "sources": [
            {
                "title": "What is a harmful algal bloom?",
                "url": "https://www.noaa.gov/what-is-harmful-algal-bloom",
                "supports": "NOAA's explanation of harmful algal blooms, their causes, colors, and possible environmental impacts."
            },
            {
                "title": "Harmful Algal Blooms (Red Tide)",
                "url": "https://oceanservice.noaa.gov/hazards/hab/",
                "supports": "NOAA's overview of harmful algal blooms and red tides, including monitoring and management."
            },
            {
                "title": "Learn about Harmful Algae, Cyanobacteria and Cyanotoxins",
                "url": "https://www.epa.gov/habs/learn-about-harmful-algae-cyanobacteria-and-cyanotoxins",
                "supports": "The US EPA's explanation of freshwater cyanobacterial blooms, discoloration, nutrient conditions, and potential toxin risks."
            }
        ]
    }
}


def evidence_catalogue_text():
    """Return topic summaries and source details for the script-writing prompt."""
    sections = []
    for name, item in TOPICS.items():
        source_lines = [
            f"- {source['title']} | {source['url']} | Supports: {source['supports']}"
            for source in item["sources"]
        ]
        sections.append(
            f"TOPIC: {name}\n"
            + "\n".join(f"- {fact}" for fact in item["evidence"])
            + "\nSOURCE OPTIONS:\n"
            + "\n".join(source_lines)
        )
    return "\n\n".join(sections)


def sources_for_topic(topic):
    """Return a copy of the curated sources for an exact topic name."""
    item = TOPICS.get(str(topic or "").strip())
    return [dict(source) for source in item["sources"]] if item else []
