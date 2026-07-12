from __future__ import annotations

from src.schemas import RipplingPositioningPillar


RIPPLING_CURRENT_POSITION = (
    "Rippling positions itself as a unified workforce platform and business operating layer, "
    "competing on consolidation, automation, shared employee data, and AI across HR, IT, spend, "
    "and finance. Its strongest marketing posture is not that it is a payroll or HCM point solution, "
    "but that it can replace fragmented tools with one system that automates work across the employee "
    "lifecycle and gives operators more control over the business."
)


RIPPLING_POSITIONING_PILLARS = [
    RipplingPositioningPillar(
        pillar="Unified HR, IT, and Finance",
        description=(
            "Rippling positions itself as a single system for managing employee data "
            "and workflows across HR, IT, and Finance."
        ),
    ),
    RipplingPositioningPillar(
        pillar="Employee lifecycle automation",
        description=(
            "Rippling automates workflows from onboarding through offboarding, including "
            "payroll, apps, devices, identity, and spend."
        ),
    ),
    RipplingPositioningPillar(
        pillar="Workflow automation",
        description="Rippling emphasizes automating manual administrative work across teams.",
    ),
    RipplingPositioningPillar(
        pillar="Global workforce management",
        description="Rippling supports global payroll, compliance, and workforce operations.",
    ),
    RipplingPositioningPillar(
        pillar="Identity, app, and device management",
        description=(
            "Rippling connects HR data to IT actions like app provisioning, device "
            "management, and access control."
        ),
    ),
    RipplingPositioningPillar(
        pillar="Spend management",
        description=(
            "Rippling connects employee data with corporate cards, expenses, approvals, "
            "and finance workflows."
        ),
    ),
]
