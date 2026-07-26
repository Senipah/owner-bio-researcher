from __future__ import annotations

import argparse
import sys
import uuid
from copy import deepcopy
from pathlib import Path
from typing import Any

from src.auth import authenticated_context
from src.browser_update import OwnerBrowserUpdater
from src.constants import OWNER_DETAIL_URL
from src.diffing import build_owner_change_plan
from src.enrichment import fetch_owner_enrichment
from src.io_utils import (
    atomic_write_json,
    new_document,
    new_owner,
    set_baseline,
    utc_now,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a reversible details and social update on a dummy owner."
    )
    parser.add_argument("--person-id", type=int, required=True)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Required confirmation that the dummy profile may be changed and restored.",
    )
    parser.add_argument("--headless", action="store_true")
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=Path("output/dummy-tests"),
    )
    return parser


def _owner_snapshot(
    person_id: int,
    details: dict[str, Any],
    socials: list[dict[str, Any]],
) -> dict[str, Any]:
    owner = new_owner(
        person_id=person_id,
        profile_url=OWNER_DETAIL_URL.format(person_id=person_id),
        report={},
    )
    owner["details"] = deepcopy(details)
    owner["social_media_profiles"] = deepcopy(socials)
    set_baseline(owner)
    owner["enrichment"] = {
        "status": "ok",
        "enriched_at": utc_now(),
        "error": None,
    }
    return owner


def _write_snapshot(path: Path, owner: dict[str, Any]) -> None:
    document = new_document()
    document["owners"] = [owner]
    atomic_write_json(path, document)


def _apply_plan(
    updater: OwnerBrowserUpdater,
    owner: dict[str, Any],
    plan: dict[str, Any],
) -> None:
    if plan["detail_changes"]:
        updater.update_details(
            profile_url=owner["profile_url"],
            changes=plan["detail_changes"],
        )
    if (
        plan["social_additions"]
        or plan["social_replacements"]
        or plan["social_removals"]
    ):
        updater.update_socials(
            profile_url=owner["profile_url"],
            additions=plan["social_additions"],
            replacements=plan["social_replacements"],
            removals=plan["social_removals"],
        )


def _social_pairs(profiles: list[dict[str, Any]]) -> list[tuple[str, str]]:
    return [
        (str(item.get("type_id", "")), str(item.get("url", "")))
        for item in profiles
    ]


def _restore_dummy(
    *,
    session,
    updater: OwnerBrowserUpdater,
    before_owner: dict[str, Any],
    artifact_dir: Path,
    report: dict[str, Any],
) -> dict[str, Any]:
    person_id = int(before_owner["person_id"])
    current_details, current_socials, _ = fetch_owner_enrichment(
        session, person_id
    )
    current_owner = _owner_snapshot(person_id, current_details, current_socials)
    _write_snapshot(artifact_dir / "pre-restore.json", current_owner)

    restore_owner = deepcopy(current_owner)
    restore_owner["details"] = deepcopy(before_owner["details"])
    restore_owner["social_media_profiles"] = deepcopy(
        before_owner["social_media_profiles"]
    )
    restore_plan = build_owner_change_plan(
        restore_owner,
        live_details=current_details,
        live_socials=current_socials,
        allow_clear=True,
        replace_socials=True,
    )
    report["restore_plan"] = restore_plan
    if restore_plan["conflicts"]:
        raise RuntimeError(f"Dummy restore conflict: {restore_plan}")
    if restore_plan["has_changes"]:
        _apply_plan(updater, restore_owner, restore_plan)

    restored_details, restored_socials, _ = fetch_owner_enrichment(
        session, person_id
    )
    if (
        restored_details != before_owner["details"]
        or _social_pairs(restored_socials)
        != _social_pairs(before_owner["social_media_profiles"])
    ):
        raise RuntimeError("Dummy profile was not restored exactly")
    restored_owner = _owner_snapshot(
        person_id, restored_details, restored_socials
    )
    report["restored_verified"] = True
    _write_snapshot(artifact_dir / "restored.json", restored_owner)
    updater.driver.get(restored_owner["profile_url"])
    updater.save_screenshot(str(artifact_dir / "restored.png"))
    return restored_owner


def main() -> int:
    args = build_parser().parse_args()
    if not args.apply:
        print(
            "Refusing to change the dummy profile without --apply.",
            file=sys.stderr,
        )
        return 2

    run_id = f"{utc_now().replace(':', '').replace('+00:00', 'Z')}-{uuid.uuid4().hex[:8]}"
    artifact_dir = args.artifact_dir / run_id
    artifact_dir.mkdir(parents=True, exist_ok=False)
    report: dict[str, Any] = {
        "person_id": args.person_id,
        "run_id": run_id,
        "started_at": utc_now(),
        "changed_verified": False,
        "restored_verified": False,
    }
    before_owner: dict[str, Any] | None = None
    restore_needed = False
    exit_code = 1

    try:
        with authenticated_context(headless=args.headless) as context:
            updater = OwnerBrowserUpdater(context.driver)
            before_details, before_socials, social_types = fetch_owner_enrichment(
                context.session, args.person_id
            )
            before_owner = _owner_snapshot(
                args.person_id, before_details, before_socials
            )
            _write_snapshot(artifact_dir / "before.json", before_owner)
            context.driver.get(before_owner["profile_url"])
            updater.save_screenshot(str(artifact_dir / "before.png"))

            if "internal_notes" not in before_owner["details"]:
                raise RuntimeError(
                    "Dummy profile details form has no internal_notes field"
                )
            marker = f"owner-bio-researcher dummy test {run_id}"
            desired_owner = deepcopy(before_owner)
            original_notes = str(
                desired_owner["details"]["internal_notes"].get("value", "")
            )
            desired_owner["details"]["internal_notes"]["value"] = (
                f"{original_notes}<p data-owner-bio-test=\"true\">{marker}</p>"
            )
            type_id = "15" if "15" in social_types else next(iter(social_types))
            desired_owner["social_media_profiles"].append(
                {
                    "profile_key": f"test_{uuid.uuid4().hex}",
                    "type_id": type_id,
                    "type": social_types[type_id],
                    "url": f"https://example.com/?owner-bio-test={uuid.uuid4().hex}",
                }
            )
            change_plan = build_owner_change_plan(
                desired_owner,
                live_details=before_details,
                live_socials=before_socials,
                allow_clear=True,
                replace_socials=False,
            )
            if change_plan["conflicts"] or not change_plan["has_changes"]:
                raise RuntimeError(f"Invalid dummy change plan: {change_plan}")
            report["change_plan"] = change_plan
            try:
                # Set before applying because a details save could succeed even
                # if a later social step fails.
                restore_needed = True
                _apply_plan(updater, desired_owner, change_plan)

                changed_details, changed_socials, _ = fetch_owner_enrichment(
                    context.session, args.person_id
                )
                verification = build_owner_change_plan(
                    desired_owner,
                    live_details=changed_details,
                    live_socials=changed_socials,
                    allow_clear=True,
                    replace_socials=False,
                )
                if verification["conflicts"] or verification["has_changes"]:
                    raise RuntimeError("Dummy changes could not be verified")
                report["changed_verified"] = True
                changed_owner = _owner_snapshot(
                    args.person_id, changed_details, changed_socials
                )
                _write_snapshot(artifact_dir / "changed.json", changed_owner)
                context.driver.get(changed_owner["profile_url"])
                updater.save_screenshot(str(artifact_dir / "changed.png"))
            finally:
                if restore_needed and before_owner is not None:
                    try:
                        _restore_dummy(
                            session=context.session,
                            updater=updater,
                            before_owner=before_owner,
                            artifact_dir=artifact_dir,
                            report=report,
                        )
                        restore_needed = False
                    except Exception as restore_exc:
                        report["restore_error"] = str(restore_exc)
                        report["manual_recovery_required"] = True
                        raise
            exit_code = 0
    except Exception as exc:
        report["error"] = str(exc)
        print(f"Dummy test failed: {exc}", file=sys.stderr)
        if restore_needed:
            report["manual_recovery_required"] = True
            print(
                f"IMPORTANT: inspect {artifact_dir / 'before.json'} and restore "
                f"dummy person {args.person_id} manually.",
                file=sys.stderr,
            )
    finally:
        report["finished_at"] = utc_now()
        atomic_write_json(artifact_dir / "report.json", report)

    print(f"Dummy test artifacts: {artifact_dir}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
