"""回归验证multidomain flow cases的正常链路、失败边界和兼容契约。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


SAMPLE_DIR = Path(__file__).parent / "multidomain_samples"


@dataclass(frozen=True)
class MultidomainFlowCase:
    """为当前测试场景提供 MultidomainFlowCase 夹具或替身。"""
    case_id: str
    filename: str
    expected_role_terms: tuple[str, ...]
    expected_direction_terms: tuple[str, ...]
    expected_intent_terms: tuple[str, ...]
    forbidden_terms: tuple[str, ...] = (
        "AI Health Algorithm",
        "Physiological Signal",
        "Biomedical AI",
        "PPG",
        "ECG",
        "Backend Engineer",
        "AI Application Engineer",
    )

    @property
    def path(self) -> Path:
        """提供 MultidomainFlowCase.path 所需的测试行为。"""
        return SAMPLE_DIR / self.filename


MULTIDOMAIN_FLOW_CASES = [
    MultidomainFlowCase(
        case_id="brand_marketing",
        filename="resume_brand_marketing_low_similarity.txt",
        expected_role_terms=("Brand Marketing", "Content Operations", "Consumer Insights"),
        expected_direction_terms=("Brand marketing", "consumer insights"),
        expected_intent_terms=("brand marketing", "content operations", "consumer insight", "campaign"),
    ),
    MultidomainFlowCase(
        case_id="museum_cultural_research",
        filename="resume_museum_cultural_research_low_similarity.txt",
        expected_role_terms=("Museum Education", "Cultural Research", "Exhibition"),
        expected_direction_terms=("Museum education", "cultural research", "public history"),
        expected_intent_terms=("museum education", "cultural research", "heritage", "archival"),
    ),
    MultidomainFlowCase(
        case_id="supply_chain_operations",
        filename="resume_supply_chain_operations_low_similarity.txt",
        expected_role_terms=("Supply Chain Operations", "Procurement", "International Trade"),
        expected_direction_terms=("Supply chain operations", "procurement", "logistics"),
        expected_intent_terms=("supply chain", "procurement", "logistics", "inventory"),
    ),
]
