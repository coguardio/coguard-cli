#!/usr/bin/env python3
"""
Helper for tests/test_reports_remain_the_same.sh to validate a scan result that was
enriched by the Trivy CVE integration (`--additional-scan-result=trivy_cve_scan`).

The CVE landscape changes daily (Trivy pulls a fresh vulnerability DB on each run), so
the set of CVE findings cannot be pinned by a checksum. Instead, this script:

  1. Splits the `failed` entries of `result.json` into CVE findings (rule name
     `cve_vuln_present`) and everything else.
  2. Computes an order-independent checksum over the non-CVE findings only. Those are
     deterministic and must stay stable across runs, just like the other checksum tests.
  3. Verifies the CVE findings structurally: there must be at least `--min-cves` of them,
     and each one has to have the shape produced by
     `TrivyCveProducer.translate_external_scan_result`. Optionally, a list of
     well-established "anchor" CVE IDs can be required to be present.

Output (stdout, single line): `<non_cve_checksum> <cve_count>`.
Exit code is non-zero if the structural checks fail (reasons go to stderr).
"""

import argparse
import hashlib
import json
import re
import sys

CVE_RULE_NAME = "cve_vuln_present"
CVE_DOC_PATTERN = re.compile(
    r"^The present project contained a HIGH or CRITICAL CVE, namely "
    r"(?P<vuln_id>[A-Za-z]+-[A-Za-z0-9-]+)\. This affects the packages .+\."
)


def non_cve_checksum(entries):
    """Order-independent sha1 over the canonical JSON form of the given entries."""
    canonical = sorted(json.dumps(entry, sort_keys=True) for entry in entries)
    return hashlib.sha1("\n".join(canonical).encode("utf-8")).hexdigest()


def validate_cve_entry(entry):
    """Returns (vuln_id, list_of_problems) for one CVE finding."""
    problems = []
    rule = entry.get("rule", {})
    if rule.get("severity") != 5:
        problems.append(f"unexpected severity {rule.get('severity')!r}")
    doc = rule.get("documentation")
    if not isinstance(doc, dict):
        return None, problems + ["documentation is not an object"]
    match = CVE_DOC_PATTERN.match(doc.get("documentation", ""))
    if not match:
        problems.append(f"documentation does not match expected format: "
                        f"{doc.get('documentation', '')[:120]!r}")
    if not doc.get("remediation"):
        problems.append("remediation is empty")
    if not isinstance(doc.get("sources"), list):
        problems.append("sources is not a list")
    return (match.group("vuln_id") if match else None), problems


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("result_json")
    parser.add_argument("--min-cves", type=int, default=1)
    parser.add_argument("--anchor-cves", default="",
                        help="Comma separated IDs that must be among the CVE findings.")
    args = parser.parse_args()

    with open(args.result_json, "r", encoding="utf-8") as stream:
        failed = json.load(stream).get("failed", [])

    cve_entries = [e for e in failed if e.get("rule", {}).get("name") == CVE_RULE_NAME]
    other_entries = [e for e in failed if e.get("rule", {}).get("name") != CVE_RULE_NAME]

    errors = []
    found_ids = set()
    for entry in cve_entries:
        vuln_id, problems = validate_cve_entry(entry)
        if vuln_id:
            found_ids.add(vuln_id)
        errors.extend(f"[{vuln_id or '?'}] {p}" for p in problems)

    if len(cve_entries) < args.min_cves:
        errors.append(f"expected at least {args.min_cves} CVE findings, "
                      f"got {len(cve_entries)} (is the Trivy integration running?)")

    anchors = {a.strip() for a in args.anchor_cves.split(",") if a.strip()}
    missing = anchors - found_ids
    if missing:
        errors.append(f"anchor CVEs missing from result: {', '.join(sorted(missing))}")

    print(f"{non_cve_checksum(other_entries)} {len(cve_entries)}")
    for err in errors:
        print(err, file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
