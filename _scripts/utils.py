"""Shared utilities for _scripts."""

import os
import sys
import re
import hashlib
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional


# Compiled regex patterns for validation
_UUID_RE = re.compile(
    r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
)
_SLUG_RE = re.compile(r'^[a-z0-9][a-z0-9\-]*$')
_PATH_RE = re.compile(r'^[a-zA-Z0-9/_\-\.]+$')


def _require_env(name: str) -> str:
    """Load required env var with a friendly error message if missing or empty."""
    value = os.environ.get(name)
    if value is None:
        print(f"Erreur : variable d'environnement absente : {name}", file=sys.stderr)
        print(f"  → Copier _scripts/.env.example vers _scripts/.env et remplir les valeurs.", file=sys.stderr)
        sys.exit(1)
    if value == "":
        print(f"Erreur : variable d'environnement vide : {name}", file=sys.stderr)
        print(f"  → Ouvrir _scripts/.env et renseigner la valeur de {name}.", file=sys.stderr)
        sys.exit(1)
    return value


def _validate_uuid(value: str) -> str:
    """Validate UUID format (any version) before use in a PostgREST URL parameter."""
    cleaned = value.strip().lower()
    if not _UUID_RE.fullmatch(cleaned):
        raise ValueError(f"Valeur UUID invalide (possible injection) : {value!r}")
    return cleaned


def _validate_path(value: str) -> str:
    """Validate an obsidian_path before use (prevents URL/injection if path reaches a query param)."""
    if not _PATH_RE.fullmatch(value):
        raise ValueError(f"obsidian_path invalide : {value!r}")
    return value


def _validate_slug(value: str) -> str:
    """Validate slug format before use in a PostgREST URL parameter."""
    if not _SLUG_RE.fullmatch(value):
        raise ValueError(f"Slug invalide : {value!r}")
    return value


def _truncate_by_section(content: str, max_chars: int) -> str:
    """Truncate Markdown content by whole ## sections to avoid cutting mid-structure."""
    if len(content) <= max_chars:
        return content

    sections = content.split('\n## ')
    result = sections[0]
    for section in sections[1:]:
        candidate = result + '\n## ' + section
        if len(candidate) <= max_chars:
            result = candidate
        else:
            break

    if len(result) > max_chars:
        result = result[:max_chars]

    return result + "\n\n_[tronqué — contexte partiel]_\n"


def normalize_for_hash(body: str) -> str:
    """Normalize content for deterministic hashing.

    Rules (from manifest hash_normalization):
    - strip leading/trailing whitespace
    - normalize \r\n -> \n
    - do NOT lowercase (preserves semantic information)
    """
    normalized = body.strip().replace("\r\n", "\n")
    return normalized


def compute_content_hash(body: str) -> str:
    """Compute deterministic SHA-256 hash of normalized content."""
    normalized = normalize_for_hash(body)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


# ============================================================
# Confidence scoring — Phase 1 Fiabilité
# ============================================================

SIGNAL_WEIGHTS: dict[str, float] = {
    "source_type_human": 0.25,
    "source_type_raw_extraction": 0.15,
    "source_type_synthesis": -0.10,
    "freshness_evergreen": 0.15,
    "freshness_volatile": 0.00,
    "freshness_deprecated": -0.30,
    "has_citations": 0.15,
    "has_source_hash": 0.10,
    "source_stale": -0.25,
    "lineage_depth_penalty_per_level": -0.05,
    "multiple_sources": 0.10,
    "human_validation": 0.20,
    "age_decay_per_month": -0.02,
    "has_summary": 0.05,
    "has_tags": 0.05,
    "review_status_draft": -0.10,
    "review_status_reviewed": 0.05,
    "review_status_verified": 0.15,
    "review_status_canonical": 0.25,
}

SOURCE_TYPE_MAP: dict[str, str] = {
    "human": "source_type_human",
    "raw": "source_type_raw_extraction",
    "extraction": "source_type_raw_extraction",
    "synthesis": "source_type_synthesis",
}


def compute_confidence_score(
    fm: dict,
    body: str,
    source_hash: str | None = None,
    source_path: str | None = None,
    vault_path: Optional[Path] = None,
    created_at: str | None = None,
) -> dict:
    """Compute a derived confidence score from multiple signals.

    Returns dict with:
      - score: float 0.0-1.0 (clamped)
      - signals: dict[str, float] — individual signal contributions
      - label: str — high/medium/low mapped from score
    """
    score = 0.5  # baseline neutral
    signals: dict[str, float] = {}

    # 1. Source type weight
    source_type = fm.get("source_type", "synthesis")
    signal_key = SOURCE_TYPE_MAP.get(source_type, "source_type_synthesis")
    weight = SIGNAL_WEIGHTS[signal_key]
    score += weight
    signals[signal_key] = weight

    # 2. Freshness
    freshness = fm.get("freshness", "volatile")
    f_key = f"freshness_{freshness}"
    f_weight = SIGNAL_WEIGHTS.get(f_key, 0.0)
    score += f_weight
    signals[f_key] = f_weight

    # 3. Citations ([[wiki links]] in body)
    body_links = extract_wiki_links(body)
    has_citations = len(body_links) >= 2
    if has_citations:
        score += SIGNAL_WEIGHTS["has_citations"]
        signals["has_citations"] = SIGNAL_WEIGHTS["has_citations"]

    # 4. Has source_hash (traceable provenance)
    if source_hash:
        score += SIGNAL_WEIGHTS["has_source_hash"]
        signals["has_source_hash"] = SIGNAL_WEIGHTS["has_source_hash"]

    # 5. Source staleness
    if source_hash and source_path and vault_path:
        stale, detail, stale_status = check_source_stale(source_hash, source_path, vault_path)
        if stale:
            score += SIGNAL_WEIGHTS["source_stale"]
            signals["source_stale"] = SIGNAL_WEIGHTS["source_stale"]

    # 6. Lineage depth
    derived_from = fm.get("derived_from", [])
    if isinstance(derived_from, list):
        depth = compute_lineage_depth(derived_from)
        penalty = SIGNAL_WEIGHTS["lineage_depth_penalty_per_level"] * depth
        if depth > 0:
            score += penalty
            signals[f"lineage_depth_{depth}"] = penalty

        # 7. Multiple sources = positive signal
        if len(derived_from) >= 2:
            score += SIGNAL_WEIGHTS["multiple_sources"]
            signals["multiple_sources"] = SIGNAL_WEIGHTS["multiple_sources"]

    # 8. Human validation signal
    status = fm.get("status", "active")
    if status == "active":
        score += SIGNAL_WEIGHTS["human_validation"] * 0.5
        signals["status_active"] = SIGNAL_WEIGHTS["human_validation"] * 0.5

    # 9. Age decay
    if created_at and freshness == "volatile":
        try:
            from datetime import datetime, timezone
            dt = datetime.fromisoformat(created_at)
            months_ago = (datetime.now(timezone.utc) - dt).days / 30.0
            if months_ago > 1:
                age_penalty = SIGNAL_WEIGHTS["age_decay_per_month"] * min(months_ago, 12)
                score += age_penalty
                signals["age_decay"] = age_penalty
        except (ValueError, TypeError):
            pass

    # 10. Has summary
    if fm.get("summary"):
        score += SIGNAL_WEIGHTS["has_summary"]
        signals["has_summary"] = SIGNAL_WEIGHTS["has_summary"]

    # 11. Has tags
    tags = fm.get("tags", [])
    if isinstance(tags, list) and len(tags) >= 1:
        score += SIGNAL_WEIGHTS["has_tags"]
        signals["has_tags"] = SIGNAL_WEIGHTS["has_tags"]

    # 12. Review status (human validation workflow)
    review_status = fm.get("review_status", "draft")
    rs_key = f"review_status_{review_status}"
    rs_weight = SIGNAL_WEIGHTS.get(rs_key, -0.10)
    score += rs_weight
    signals[rs_key] = rs_weight

    # Clamp to [0.0, 1.0]
    score = max(0.0, min(1.0, score))

    # Map to label
    if score >= 0.65:
        label = "high"
    elif score >= 0.35:
        label = "medium"
    else:
        label = "low"

    return {
        "score": round(score, 4),
        "signals": signals,
        "label": label,
    }


def compute_lineage_depth(derived_from: list) -> int:
    """Compute derivation depth from provenance chain.

    Levels:
      0 — no derived_from (human-written original)
      1 — directly from raw/ (source or extraction)
      2 — enriched from other wiki notes (enriched_by, extends)
      3+ — further derivations
    """
    if not derived_from:
        return 0

    max_depth = 0
    for entry in derived_from:
        if isinstance(entry, dict):
            rel = entry.get("relation", "source")
            path = entry.get("path", "")
        else:
            rel = "source"
            path = str(entry)

        if rel == "source" and path.startswith("raw/"):
            depth = 1
        elif rel == "source":
            depth = 1
        elif rel in ("enriched_by", "extends"):
            depth = 2
        elif rel == "relates_to":
            depth = 1
        else:
            depth = 1

        max_depth = max(max_depth, depth)

    return max_depth


def check_source_stale(
    source_hash: str | None,
    source_path: str | None,
    vault_path: Path,
) -> tuple[bool, str, str | None]:
    """Check if a source file has been modified since ingestion.

    Returns (is_stale: bool, detail: str, stale_status: str | None).
    stale_status is one of 'stale', 'needs_reingest', 'partially_outdated', or None.
    """
    if not source_hash or not source_path:
        return False, "No source provenance", None

    full_path = vault_path / source_path
    if not full_path.exists():
        return True, f"Source file not found: {source_path}", "needs_reingest"

    try:
        raw_body = full_path.read_text(encoding="utf-8")
        current_hash = compute_content_hash(extract_body(raw_body))
        if current_hash != source_hash:
            return (
                True,
                f"Source hash mismatch: stored={source_hash[:12]}... current={current_hash[:12]}...",
                "partially_outdated",
            )
        return False, "Source unchanged", None
    except Exception as e:
        return True, f"Error reading source: {e}", "stale"


# Pydantic models for data validation
class WikiNote(BaseModel):
    obsidian_path: str = Field(..., description="Path to the note file")
    title: str = Field(..., description="Note title")
    content: str = Field("", description="Note content")
    tags: List[str] = Field(default_factory=list, description="Tags list")
    type: str = Field("note", description="Note type")
    status: str = Field("active", description="Note status")
    date: Optional[str] = Field(None, description="Creation/update date")
    schema_version: str = Field("3.0.0", description="Schema version")
    content_hash: Optional[str] = Field(None, description="SHA-256 hash of content")
    source_hash: Optional[str] = Field(None, description="SHA-256 hash of source")
    source_path: Optional[str] = Field(None, description="Path to source file")
    links_to: List[str] = Field(default_factory=list, description="Wiki links to other notes")
    canonical_slug: Optional[str] = Field(None, description="Canonical slug for this note")
    token_count: Optional[int] = Field(None, description="Approximate token count")
    summary: Optional[str] = Field(None, description="Auto-generated summary")
    last_ingested_at: Optional[str] = Field(None, description="Last ingestion ISO timestamp")
    freshness: str = Field("volatile", description="Freshness classification")
    memory_tier: str = Field("working", description="Memory tier")
    decay_score: float = Field(0.0, description="Decay score")
    sensitivity: str = Field("internal", description="Sensitivity level")
    confidence: str = Field("medium", description="Confidence level (human-declared)")
    confidence_score: Optional[float] = Field(None, description="Derived confidence score 0.0-1.0")
    confidence_signals: Optional[dict] = Field(None, description="Signal breakdown for confidence score")
    lineage_depth: int = Field(0, description="Derivation depth (0=human original)")
    derived_from: list = Field(default_factory=list, description="Provenance chain")
    review_status: str = Field("draft", description="Human validation status: draft/reviewed/verified/canonical")
    stale_status: Optional[str] = Field(None, description="Staleness status: stale/needs_reingest/partially_outdated")
    stale_reason: Optional[str] = Field(None, description="Reason for staleness")
    source_type: str = Field("synthesis", description="Source type")

    model_config = ConfigDict(validate_assignment=True)


class BrainMemory(BaseModel):
    type: str = Field(..., description="Memory type (preference, decision, etc.)")
    content: str = Field(..., description="Memory content")
    created_at: str = Field(..., description="Creation timestamp")

    model_config = ConfigDict(validate_assignment=True)


# ============================================================
# Shared constants & functions — factorisées depuis sync.py/lint.py/embed.py
# ============================================================

_YAML_SPECIAL_CHARS = set(':#[]{}|>&*!,?')
EXCLUDED_SCAN_DIRS = {"_system", "_meta", "_staging", "_compressed"}


def _strip_bom(text: str) -> str:
    """Strip UTF-8 BOM from text."""
    return text.lstrip('\ufeff')


def parse_frontmatter(content: str, strip_bom: bool = False) -> dict:
    """Parse YAML frontmatter. Handles inline lists, indented lists, and quoted values."""
    if strip_bom:
        content = _strip_bom(content)
    lines = content.split('\n')
    if not lines or lines[0].strip() != '---':
        return {}

    fm: dict = {}
    i = 1
    current_key: str | None = None
    current_list: list | None = None

    while i < len(lines):
        line = lines[i]
        if line.strip() == '---':
            break

        stripped = line.strip()

        if stripped.startswith('- ') and current_key is not None and current_list is not None:
            current_list.append(stripped[2:].strip().strip('"\''))
            i += 1
            continue

        if ':' in line and not line[0].isspace():
            if current_key is not None and current_list is not None:
                fm[current_key] = current_list if current_list else []

            key, _, value = line.partition(':')
            key = key.strip()
            value = value.strip()

            if value == '':
                current_key = key
                current_list = []
                fm[key] = []
            elif value.startswith('[') and value.endswith(']'):
                current_key = key
                current_list = None
                inner = value[1:-1]
                fm[key] = [v.strip().strip('"\'') for v in inner.split(',') if v.strip()]
            else:
                current_key = key
                current_list = None
                if len(value) >= 2 and value[0] in ('"', "'") and value[-1] == value[0]:
                    value = value[1:-1]
                fm[key] = value

        i += 1

    if current_key is not None and current_list is not None:
        fm[current_key] = current_list if current_list else []

    return fm


def extract_body(content: str) -> str:
    """Extract body text after frontmatter block."""
    m = re.match(r"^---\s*\n.*?\n---(?:\s*\n|$)(.*)$", content, re.DOTALL)
    if m:
        return m.group(1).strip()
    return content.strip()


def extract_wiki_links(body: str) -> list[str]:
    """Extract deduplicated [[wiki links]] targets from body text."""
    pattern = re.compile(r'\[\[([^\]]+?)(?:\|[^\]]+)?\]\]')
    seen = set()
    result = []
    for match in pattern.finditer(body):
        target = match.group(1).strip()
        if '/' in target:
            target = target.rsplit('/', 1)[1]
        if target.endswith('.md'):
            target = target[:-3]
        if target and target not in seen:
            seen.add(target)
            result.append(target)
    return result


def build_frontmatter(fm: dict) -> str:
    """Serialise dict to valid YAML frontmatter block.
    Handles nested dicts, structured derived_from, lists, and special characters."""
    lines = ['---']
    for key, value in fm.items():
        if key == "derived_from" and isinstance(value, list):
            lines.append("derived_from:")
            for item in value:
                if isinstance(item, dict):
                    lines.append(f'  - path: {item.get("path", "")}')
                    lines.append(f'    relation: {item.get("relation", "source")}')
                else:
                    lines.append(f'  - {item}')
        elif isinstance(value, dict):
            lines.append(f'{key}:')
            for k, v in value.items():
                v_str = str(v)
                if isinstance(v, float):
                    v_str = f"{v}"
                lines.append(f'  {k}: {v_str}')
        elif isinstance(value, list):
            if value:
                lines.append(f'{key}:')
                for item in value:
                    lines.append(f'  - {item}')
            else:
                lines.append(f'{key}: []')
        else:
            str_val = str(value)
            if any(c in str_val for c in _YAML_SPECIAL_CHARS) or str_val != str_val.strip():
                str_val = '"' + str_val.replace('\\', '\\\\').replace('"', '\\"') + '"'
            lines.append(f'{key}: {str_val}')
    lines.append('---')
    return '\n'.join(lines)
