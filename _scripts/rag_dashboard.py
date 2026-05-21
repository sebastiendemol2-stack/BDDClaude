"""RAG Dashboard — observabilité des retrievals.

Usage:
    python rag_dashboard.py --stats          Show aggregated statistics
    python rag_dashboard.py --recent [N]     Show last N retrievals
    python rag_dashboard.py --anomalies      Detect drift (latency >2x, fallback >30%)
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime, timezone, timedelta
from collections import Counter

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env", override=True)

_VAULT_PATH = Path(os.environ.get("VAULT_PATH", str(Path(__file__).parent.parent))).resolve()
LOG_DIR = _VAULT_PATH / "wiki" / "_system" / "logs"


def _load_logs(days: int = 30) -> list[dict]:
    """Load all RAG log entries from the last N days."""
    entries = []
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    log_dir = LOG_DIR
    if not log_dir.exists():
        return entries

    for log_file in sorted(log_dir.glob("rag_*.jsonl")):
        try:
            for line in log_file.read_text(encoding="utf-8").strip().split("\n"):
                if not line.strip():
                    continue
                entry = json.loads(line)
                ts = datetime.fromisoformat(entry["timestamp"])
                if ts >= cutoff:
                    entries.append(entry)
        except Exception:
            continue

    return entries


def _stats(entries: list[dict]) -> dict:
    """Compute aggregated statistics from log entries."""
    if not entries:
        return {"status": "no data", "entries": 0}

    total = len(entries)
    fallback_count = sum(1 for e in entries if e.get("fallback"))
    latencies = [e["latency_ms"] for e in entries if "latency_ms" in e]
    top_k_counts = Counter(e.get("top_k", 0) for e in entries)
    queries_by_day = Counter(e["timestamp"][:10] for e in entries)

    # Top queried sources
    source_counter: Counter = Counter()
    for e in entries:
        for r in e.get("results", []):
            source_counter[r.get("path", "unknown")] += 1

    return {
        "status": "ok",
        "entries": total,
        "date_range": f"{entries[0]['timestamp'][:10]} to {entries[-1]['timestamp'][:10]}",
        "fallback_ratio": round(fallback_count / total, 3) if total else 0,
        "avg_latency_ms": round(sum(latencies) / len(latencies), 1) if latencies else 0,
        "max_latency_ms": round(max(latencies), 1) if latencies else 0,
        "queries_per_day": dict(sorted(queries_by_day.items())),
        "top_sources": source_counter.most_common(10),
    }


def _recent(entries: list[dict], n: int = 10) -> list[dict]:
    """Return the N most recent log entries."""
    sorted_entries = sorted(entries, key=lambda e: e["timestamp"], reverse=True)
    return sorted_entries[:n]


def _anomalies(entries: list[dict]) -> list[dict]:
    """Detect anomalous retrievals: high latency, high fallback ratio, empty results."""
    if not entries:
        return []

    latencies = [e["latency_ms"] for e in entries if "latency_ms" in e]
    avg_lat = sum(latencies) / len(latencies) if latencies else 0
    threshold_latency = avg_lat * 2

    fallback_entries = sum(1 for x in entries if x.get("fallback"))
    high_fallback = fallback_entries / len(entries) > 0.3 if entries else False

    anomalies = []
    for e in entries:
        reasons = []
        if threshold_latency > 0 and e.get("latency_ms", 0) > threshold_latency:
            reasons.append(f"latency {e['latency_ms']:.0f}ms > {threshold_latency:.0f}ms")
        if e.get("fallback") and high_fallback:
            reasons.append("fallback (window ratio {:.0f}%)".format(
                fallback_entries / len(entries) * 100))
        if not e.get("results"):
            reasons.append("empty results")

        if reasons:
            anomalies.append({
                "timestamp": e["timestamp"],
                "query": e.get("query", ""),
                "reasons": reasons,
            })

    return anomalies


def cmd_stats(entries: list[dict]) -> None:
    stats = _stats(entries)
    print("=== RAG Dashboard — Stats ===")
    print(f"Status:           {stats['status']}")
    print(f"Entries:          {stats['entries']}")
    print(f"Date range:       {stats.get('date_range', 'N/A')}")
    print(f"Fallback ratio:   {stats.get('fallback_ratio', 'N/A')}")
    print(f"Avg latency:      {stats.get('avg_latency_ms', 'N/A')} ms")
    print(f"Max latency:      {stats.get('max_latency_ms', 'N/A')} ms")
    print(f"\nQueries per day:")
    for day, count in stats.get("queries_per_day", {}).items():
        print(f"  {day}: {count}")
    print(f"\nTop sources:")
    for src, count in stats.get("top_sources", []):
        print(f"  {src}: {count}")


def cmd_recent(entries: list[dict], n: int) -> None:
    recent = _recent(entries, n)
    if not recent:
        print("No recent entries.")
        return
    print(f"=== Last {len(recent)} Retrievals ===")
    for e in recent:
        tag = " [FALLBACK]" if e.get("fallback") else ""
        lat = f"{e.get('latency_ms', 0):.0f}ms"
        top = e.get("top_k", 0)
        q = e.get("query", "")[:60]
        print(f"  {e['timestamp'][:19]} | {lat:>7} | top={top} |{tag} {q}")


def cmd_anomalies(entries: list[dict]) -> None:
    anoms = _anomalies(entries)
    if not anoms:
        print("No anomalies detected.")
        return
    print(f"=== {len(anoms)} Anomalies ===")
    for a in anoms:
        print(f"  {a['timestamp'][:19]} | {'; '.join(a['reasons'])}")
        print(f"    query: {a['query'][:80]}")


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="RAG Dashboard")
    parser.add_argument("--days", type=int, default=30, help="Lookback window in days")
    parser.add_argument("--stats", action="store_true", help="Show aggregated statistics")
    parser.add_argument("--recent", nargs="?", type=int, const=10, default=None,
                        help="Show last N retrievals")
    parser.add_argument("--anomalies", action="store_true", help="Detect drift and anomalies")

    args = parser.parse_args()

    entries = _load_logs(days=args.days)
    if not entries:
        print("No log entries found in the last", args.days, "days.")
        return

    if args.stats:
        cmd_stats(entries)
    elif args.recent is not None:
        cmd_recent(entries, args.recent)
    elif args.anomalies:
        cmd_anomalies(entries)
    else:
        cmd_stats(entries)
        print()
        cmd_recent(entries, 5)


if __name__ == "__main__":
    main()
