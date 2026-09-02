from __future__ import annotations

from src.vessel_owner_order import (
    build_vessel_owner_order_plan,
    parse_vessel_owner_order,
    submit_vessel_owner_order,
)


HTML = """
<fieldset>
  <legend>[NEW] Ultimate Beneficial Owners</legend>
  <table class="jsYayContactExternalRelationshipTable">
    <tbody>
      <tr class="jsExternalRelationshipItem" data-id="30"
          data-base_entity_type_id="1" data-start_year="2005"
          data-start_month="2" data-start_day="">
        <td>Newest</td><td>2005</td><td></td><td>Current</td>
      </tr>
      <tr class="jsExternalRelationshipItem" data-id="10"
          data-base_entity_type_id="2" data-start_year="1980"
          data-start_month="" data-start_day="">
        <td>Oldest</td><td>1980</td><td>1990</td><td>Former</td>
      </tr>
      <tr class="jsExternalRelationshipItem" data-id="40"
          data-base_entity_type_id="1" data-start_year=""
          data-start_month="" data-start_day="">
        <td>Undated first</td><td></td><td></td><td></td>
      </tr>
      <tr class="jsExternalRelationshipItem" data-id="20"
          data-base_entity_type_id="1" data-start_year="2005"
          data-start_month="1" data-start_day="15">
        <td>Middle</td><td>15/01/2005</td><td></td><td></td>
      </tr>
      <tr class="jsExternalRelationshipItem" data-id="50"
          data-base_entity_type_id="1" data-start_year=""
          data-start_month="" data-start_day="">
        <td>Undated second</td><td></td><td></td><td></td>
      </tr>
    </tbody>
  </table>
</fieldset>
<fieldset>
  <legend>Registered Owners</legend>
  <table class="jsYayContactExternalRelationshipTable">
    <tbody>
      <tr class="jsExternalRelationshipItem" data-id="999">
        <td>Wrong table</td><td></td><td></td><td></td>
      </tr>
    </tbody>
  </table>
</fieldset>
"""


def test_parser_reads_only_ubo_rows_in_display_order() -> None:
    relationships = parse_vessel_owner_order(HTML)

    assert [item["relationship_id"] for item in relationships] == [
        30,
        10,
        40,
        20,
        50,
    ]
    assert relationships[0]["start_month"] == 2
    assert relationships[0]["start_day"] is None
    assert relationships[1]["entity_type_id"] == "2"


def test_plan_matches_site_date_sort_and_is_stable_for_undated_rows() -> None:
    plan = build_vessel_owner_order_plan(parse_vessel_owner_order(HTML))

    assert plan["has_changes"] is True
    assert plan["target_relationship_ids"] == [10, 20, 30, 40, 50]
    assert {item["relationship_id"] for item in plan["moves"]} == {
        10,
        20,
        30,
        40,
    }


class _Response:
    text = '{"success":true}'

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, bool]:
        return {"success": True}


class _Session:
    def __init__(self) -> None:
        self.call: dict | None = None

    def patch(self, url: str, **kwargs) -> _Response:
        self.call = {"url": url, **kwargs}
        return _Response()


def test_submit_uses_native_complete_order_patch_contract() -> None:
    session = _Session()

    submit_vessel_owner_order(
        session,
        vessel_id=47984,
        relationship_ids=[10, 20, 30],
    )

    assert session.call is not None
    assert session.call["params"] == [
        ("order[]", "10"),
        ("order[]", "20"),
        ("order[]", "30"),
        ("role_id", "1"),
        ("external_id", "47984"),
    ]
