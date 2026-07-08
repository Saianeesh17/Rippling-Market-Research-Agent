from __future__ import annotations

from typing import Dict, List

from src.config import utc_now_iso
from src.schemas import SourceRecord


DUMMY_COMPETITOR_DATA: Dict[str, Dict[str, object]] = {
    "gusto": {
        "name": "Gusto",
        "domain": "gusto.com",
        "category": "Payroll / HR / Benefits",
        "description": "Payroll and HR platform for small and growing businesses",
        "confidence": 0.9,
        "primary_positioning": "Simple payroll, HR, benefits, and compliance support for small businesses.",
        "personas": ["small business owner", "HR admin"],
        "segments": ["SMB", "growing companies"],
        "differentiators": ["ease of use", "compliance support", "all-in-one HR"],
        "themes": [
            {
                "theme": "payroll simplicity",
                "keywords": ["simple payroll", "payroll", "payday"],
                "claim": "Gusto emphasizes simple payroll and HR for small businesses.",
                "persona": "small business owner",
                "funnel_stage": "awareness",
            },
            {
                "theme": "HR and benefits for SMBs",
                "keywords": ["benefits", "small businesses", "HR"],
                "claim": "Gusto ties payroll to HR, benefits, onboarding, and compliance for SMB buyers.",
                "persona": "HR admin",
                "funnel_stage": "consideration",
            },
            {
                "theme": "pricing packaging caveat",
                "keywords": ["pricing", "tier", "third-party pricing", "public pricing"],
                "claim": "Gusto pricing evidence is partial in this dummy dataset and includes lower-confidence third-party estimates.",
                "persona": "small business owner",
                "funnel_stage": "consideration",
            },
        ],
        "gap": "Limited visible emphasis on IT, device management, app provisioning, finance workflows, and cross-functional lifecycle automation.",
        "recent_change": "Recent public-style sources show a contractor payments and compliance messaging push.",
        "opportunity": "Position Rippling as the broader workforce platform for companies that have outgrown payroll-only tools.",
    },
    "deel": {
        "name": "Deel",
        "domain": "deel.com",
        "category": "Global Payroll / Contractor Management",
        "description": "Global hiring, payroll, and contractor management platform for distributed teams",
        "confidence": 0.9,
        "primary_positioning": "Global hiring, contractor management, international payroll, and compliance for distributed teams.",
        "personas": ["people operations leader", "global hiring manager", "finance leader"],
        "segments": ["distributed teams", "global companies", "mid-market"],
        "differentiators": ["global coverage", "contractor workflows", "compliance"],
        "themes": [
            {
                "theme": "global hiring",
                "keywords": ["global hiring", "international payroll", "distributed teams"],
                "claim": "Deel emphasizes global hiring, contractor management, and international payroll.",
                "persona": "people operations leader",
                "funnel_stage": "awareness",
            },
            {
                "theme": "compliance",
                "keywords": ["compliance", "contractor", "localized"],
                "claim": "Deel messaging repeatedly connects distributed workforce operations with compliance support.",
                "persona": "global hiring manager",
                "funnel_stage": "consideration",
            },
            {
                "theme": "pricing packaging caveat",
                "keywords": ["pricing", "package", "demo", "contact sales"],
                "claim": "Deel pricing and packaging evidence is strongest where official public pages describe packages, with exact enterprise pricing still caveated.",
                "persona": "finance leader",
                "funnel_stage": "consideration",
            },
        ],
        "gap": "Less public emphasis on device management, app provisioning, and finance workflows beyond global workforce operations.",
        "recent_change": "Recent public-style sources show continued expansion around global payroll and compliance categories.",
        "opportunity": "Use a nuanced angle: match global workforce credibility while showing how HR data can also trigger IT and finance workflows.",
    },
    "bamboohr": {
        "name": "BambooHR",
        "domain": "bamboohr.com",
        "category": "HRIS / People Operations",
        "description": "HR software for people operations, employee experience, and HRIS simplicity",
        "confidence": 0.9,
        "primary_positioning": "HRIS simplicity, employee experience, and people operations for HR teams.",
        "personas": ["HR leader", "people operations manager"],
        "segments": ["SMB", "mid-market HR teams"],
        "differentiators": ["HRIS simplicity", "employee experience", "people data"],
        "themes": [
            {
                "theme": "HRIS simplicity",
                "keywords": ["HR software", "HRIS", "people operations", "employee experience"],
                "claim": "BambooHR emphasizes HR software, HRIS simplicity, employee experience, and people operations.",
                "persona": "HR leader",
                "funnel_stage": "awareness",
            },
            {
                "theme": "people operations",
                "keywords": ["people", "onboarding", "employee"],
                "claim": "BambooHR's public-style messaging centers HR teams and employee lifecycle moments within HR.",
                "persona": "people operations manager",
                "funnel_stage": "consideration",
            },
            {
                "theme": "pricing packaging caveat",
                "keywords": ["pricing", "quote", "package"],
                "claim": "BambooHR pricing evidence is partial because exact packages are represented as public quote-oriented information.",
                "persona": "HR leader",
                "funnel_stage": "consideration",
            },
        ],
        "gap": "Limited public messaging around IT, finance, identity, device management, and cross-functional employee lifecycle automation.",
        "recent_change": "Recent public-style sources show employee experience and onboarding messaging.",
        "opportunity": "Position Rippling as HRIS plus the IT and finance actions that happen around every employee change.",
    },
    "generic": {
        "name": "Unknown Competitor",
        "domain": None,
        "category": "HR / Payroll Software",
        "description": "Generic HR or payroll software competitor inferred from ambiguous input",
        "confidence": 0.55,
        "primary_positioning": "Generic HR, payroll, and workforce administration messaging.",
        "personas": ["HR admin"],
        "segments": ["SMB"],
        "differentiators": ["ease of use", "HR administration"],
        "themes": [
            {
                "theme": "generic HR payroll",
                "keywords": ["payroll", "HR", "workforce"],
                "claim": "The unknown competitor appears to use generic HR and payroll messaging in the dummy fallback dataset.",
                "persona": "HR admin",
                "funnel_stage": "awareness",
            },
            {
                "theme": "pricing packaging caveat",
                "keywords": ["pricing", "third-party"],
                "claim": "Pricing evidence for the unknown competitor is low-confidence fallback data.",
                "persona": "HR admin",
                "funnel_stage": "consideration",
            },
        ],
        "gap": "Fallback sources provide limited evidence for IT, finance, device management, and lifecycle automation messaging.",
        "recent_change": "No strong recent-change signal is available in the fallback dataset.",
        "opportunity": "Use broad workforce platform positioning, but keep confidence lower until stronger sources are available.",
    },
}


def slugify(value: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "_" for ch in value).strip("_")


def competitor_key(name: str) -> str:
    lowered = name.lower()
    if "gusto" in lowered:
        return "gusto"
    if "deel" in lowered:
        return "deel"
    if "bamboo" in lowered:
        return "bamboohr"
    return "generic"


def get_competitor_data(name: str) -> Dict[str, object]:
    return DUMMY_COMPETITOR_DATA[competitor_key(name)]


def build_source(
    competitor_name: str,
    tool_name: str,
    category: str,
    title: str,
    content: str,
    source_type: str,
    reliability_weight: float,
    *,
    url_path: str = "",
    publisher: str | None = None,
    is_official: bool = False,
    is_third_party: bool = False,
    published_at: str | None = None,
    notes: str | None = None,
) -> SourceRecord:
    data = get_competitor_data(competitor_name)
    canonical_name = str(data["name"])
    domain = data.get("domain")
    source_slug = slugify(f"{canonical_name}_{tool_name}_{category}_{title}")[:96]
    url = None
    if domain and (is_official or url_path):
        path = url_path or f"/dummy/{slugify(title)}"
        url = f"https://{domain}{path}"
    elif is_third_party:
        url = f"https://example-public-source.test/{slugify(canonical_name)}/{slugify(title)}"

    confidence_modifier = 0.92 if is_official else 0.68 if is_third_party else 0.75
    return SourceRecord(
        source_id=source_slug,
        competitor_name=canonical_name,
        source_type=category,
        title=title,
        url=url,
        content=content,
        publisher=publisher or (canonical_name if is_official else "Public third-party source"),
        is_official=is_official,
        is_third_party=is_third_party,
        is_public=True,
        published_at=published_at,
        discovered_at=utc_now_iso(),
        discovery_tool=tool_name,
        reliability_weight=reliability_weight,
        relevance_score=0.5,
        confidence_modifier=confidence_modifier,
        notes=notes,
    )


def content_for(name: str, purpose: str) -> str:
    data = get_competitor_data(name)
    cname = str(data["name"])
    if purpose == "homepage":
        return (
            f"{cname} positions itself around {data['primary_positioning']} "
            f"Target personas include {', '.join(data['personas'])}. "
            f"Target segments include {', '.join(data['segments'])}."
        )
    if purpose == "product":
        return (
            f"{cname} product pages emphasize {data['primary_positioning']} "
            "The pages describe onboarding, compliance, core workflows, and admin efficiency."
        )
    if purpose == "pricing":
        return (
            f"{cname} public pricing and packaging content references pricing tiers, packages, "
            "demo/contact-sales motion, or buying-plan details where available."
        )
    if purpose == "third_party_pricing":
        return (
            f"A public third-party pricing page gives lower-confidence pricing context for {cname}. "
            "This dummy source should be caveated and weighted below official competitor pages."
        )
    if purpose == "ads":
        return f"{cname} ad copy repeats campaign hooks from its positioning: {data['primary_positioning']}"
    if purpose == "social":
        return f"{cname} social posts highlight public campaign themes, compliance reminders, and product education."
    if purpose == "press":
        return f"{cname} announcement-style content says: {data['recent_change']}"
    if purpose == "comparison":
        return (
            f"{cname} comparison content frames buying criteria around {data['primary_positioning']} "
            "and handles objections about switching from alternative tools."
        )
    return f"{cname} public dummy source content for {purpose}."


def theme_keywords(name: str) -> List[str]:
    data = get_competitor_data(name)
    keywords: List[str] = []
    for theme in data["themes"]:
        keywords.extend(theme["keywords"])
    return keywords

