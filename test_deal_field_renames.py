"""
Test entity field renames for Pipedrive v2 migration.
Covers all entities via the generic rewrite_entity_field_references.
"""
import json
from migrate_pipedrive import (
    rewrite_entity_field_references, rewrite_deal_field_references,
    find_module_ids_by_names, find_deal_module_ids,
    DEAL_FIELD_RENAMES, DEAL_FLATTENED_OBJECT_FIELDS, DEAL_MODULE_NAMES,
    PERSON_FIELD_RENAMES, PERSON_FLATTENED_OBJECT_FIELDS, PERSON_MODULE_NAMES,
    ORG_FIELD_RENAMES, ORG_FLATTENED_OBJECT_FIELDS, ORG_MODULE_NAMES,
    ACTIVITY_FIELD_RENAMES, ACTIVITY_FLATTENED_OBJECT_FIELDS, ACTIVITY_MODULE_NAMES,
    PRODUCT_FIELD_RENAMES, PRODUCT_FLATTENED_OBJECT_FIELDS, PRODUCT_MODULE_NAMES,
    DEAL_PRODUCT_FIELD_RENAMES, DEAL_PRODUCT_FLATTENED_OBJECT_FIELDS, DEAL_PRODUCT_MODULE_NAMES,
    PIPELINE_FIELD_RENAMES, PIPELINE_FLATTENED_OBJECT_FIELDS, PIPELINE_MODULE_NAMES,
    STAGE_FIELD_RENAMES, STAGE_FLATTENED_OBJECT_FIELDS, STAGE_MODULE_NAMES,
    ENTITY_RENAME_CONFIGS,
)


def _run_renames(blueprint, entity_label, module_names, field_renames, flattened):
    """Helper: find module IDs and apply renames."""
    blueprint_str = json.dumps(blueprint)
    ids = find_module_ids_by_names(blueprint['flow'], module_names)
    result_str, count = rewrite_entity_field_references(
        blueprint_str, ids, field_renames, flattened, entity_label
    )
    return json.loads(result_str), count


# ========================== DEAL TESTS ==========================

def test_deal_simple_renames():
    bp = {"flow": [
        {"id": 2, "module": "pipedrive:getDealV2", "mapper": {}},
        {"id": 5, "module": "util:Set", "mapper": {
            "a": "{{2.user_id}}", "b": "{{2.deleted}}", "c": "{{2.label}}", "d": "{{2.cc_email}}"
        }}
    ]}
    result, count = _run_renames(bp, 'Deal', DEAL_MODULE_NAMES, DEAL_FIELD_RENAMES, DEAL_FLATTENED_OBJECT_FIELDS)
    m = result['flow'][1]['mapper']
    assert m['a'] == '{{2.owner_id}}' and m['b'] == '{{2.is_deleted}}'
    assert m['c'] == '{{2.label_ids}}' and m['d'] == '{{2.smart_bcc_email}}'
    assert count == 4
    print("[PASS] test_deal_simple_renames")


def test_deal_flattened():
    bp = {"flow": [
        {"id": 10, "module": "pipedrive:getDealV2", "mapper": {}},
        {"id": 11, "module": "util:Set", "mapper": {
            "a": "{{10.org_id.name}}", "b": "{{10.creator_user_id.name}}",
            "c": "{{10.user_id.name}}", "d": "{{10.user_id.value}}"
        }}
    ]}
    result, count = _run_renames(bp, 'Deal', DEAL_MODULE_NAMES, DEAL_FIELD_RENAMES, DEAL_FLATTENED_OBJECT_FIELDS)
    m = result['flow'][1]['mapper']
    assert m['a'] == '{{10.org_id}}' and m['b'] == '{{10.creator_user_id}}'
    assert m['c'] == '{{10.owner_id}}' and m['d'] == '{{10.owner_id}}'
    print("[PASS] test_deal_flattened")


def test_deal_no_false_positives():
    bp = {"flow": [
        {"id": 3, "module": "pipedrive:GetPersonV2", "mapper": {}},
        {"id": 4, "module": "util:Set", "mapper": {"a": "{{3.user_id}}"}}
    ]}
    result, count = _run_renames(bp, 'Deal', DEAL_MODULE_NAMES, DEAL_FIELD_RENAMES, DEAL_FLATTENED_OBJECT_FIELDS)
    assert result['flow'][1]['mapper']['a'] == '{{3.user_id}}' and count == 0
    print("[PASS] test_deal_no_false_positives")


# ========================== PERSON TESTS ==========================

def test_person_simple_renames():
    bp = {"flow": [
        {"id": 15, "module": "pipedrive:GetPersonV2", "mapper": {}},
        {"id": 16, "module": "util:Set", "mapper": {
            "a": "{{15.phone}}", "b": "{{15.email}}", "c": "{{15.im}}",
            "d": "{{15.active_flag}}", "e": "{{15.label}}", "f": "{{15.name}}"
        }}
    ]}
    result, count = _run_renames(bp, 'Person', PERSON_MODULE_NAMES, PERSON_FIELD_RENAMES, PERSON_FLATTENED_OBJECT_FIELDS)
    m = result['flow'][1]['mapper']
    assert m['a'] == '{{15.phones}}' and m['b'] == '{{15.emails}}' and m['c'] == '{{15.ims}}'
    assert m['d'] == '{{15.is_deleted}}' and m['e'] == '{{15.label_ids}}'
    assert m['f'] == '{{15.name}}'  # name should NOT be renamed
    assert count == 5  # 5 renames, 'name' untouched
    print("[PASS] test_person_simple_renames")


def test_person_flattened():
    bp = {"flow": [
        {"id": 25, "module": "pipedrive:GetPersonV2", "mapper": {}},
        {"id": 26, "module": "util:Set", "mapper": {
            "a": "{{25.owner_id.name}}", "b": "{{25.org_id.name}}", "c": "{{25.picture_id.url}}"
        }}
    ]}
    result, count = _run_renames(bp, 'Person', PERSON_MODULE_NAMES, PERSON_FIELD_RENAMES, PERSON_FLATTENED_OBJECT_FIELDS)
    m = result['flow'][1]['mapper']
    assert m['a'] == '{{25.owner_id}}' and m['b'] == '{{25.org_id}}' and m['c'] == '{{25.picture_id}}'
    print("[PASS] test_person_flattened")


# ========================== ORGANIZATION TESTS ==========================

def test_org_renames():
    bp = {"flow": [
        {"id": 30, "module": "pipedrive:getOrganizationV2", "mapper": {}},
        {"id": 31, "module": "util:Set", "mapper": {
            "a": "{{30.active_flag}}", "b": "{{30.label}}", "c": "{{30.owner_id.name}}"
        }}
    ]}
    result, count = _run_renames(bp, 'Org', ORG_MODULE_NAMES, ORG_FIELD_RENAMES, ORG_FLATTENED_OBJECT_FIELDS)
    m = result['flow'][1]['mapper']
    assert m['a'] == '{{30.is_deleted}}', f"active_flag not renamed: {m['a']}"
    assert m['b'] == '{{30.label_ids}}', f"label not renamed: {m['b']}"
    assert m['c'] == '{{30.owner_id}}', f"owner_id.name not flattened: {m['c']}"
    print("[PASS] test_org_renames")


# ========================== ACTIVITY TESTS ==========================

def test_activity_renames():
    bp = {"flow": [
        {"id": 40, "module": "pipedrive:getActivityV2", "mapper": {}},
        {"id": 41, "module": "util:Set", "mapper": {
            "a": "{{40.busy_flag}}", "b": "{{40.created_by_user_id}}",
            "c": "{{40.user_id}}", "d": "{{40.user_id.name}}"
        }}
    ]}
    result, count = _run_renames(bp, 'Activity', ACTIVITY_MODULE_NAMES, ACTIVITY_FIELD_RENAMES, ACTIVITY_FLATTENED_OBJECT_FIELDS)
    m = result['flow'][1]['mapper']
    assert m['a'] == '{{40.busy}}', f"busy_flag not renamed: {m['a']}"
    assert m['b'] == '{{40.creator_user_id}}', f"created_by_user_id not renamed: {m['b']}"
    assert m['c'] == '{{40.owner_id}}', f"user_id not renamed: {m['c']}"
    assert m['d'] == '{{40.owner_id}}', f"user_id.name not flattened+renamed: {m['d']}"
    print("[PASS] test_activity_renames")


# ========================== PRODUCT TESTS ==========================

def test_product_renames():
    bp = {"flow": [
        {"id": 50, "module": "pipedrive:getProductV2", "mapper": {}},
        {"id": 51, "module": "util:Set", "mapper": {
            "a": "{{50.selectable}}", "b": "{{50.active_flag}}", "c": "{{50.owner_id.name}}"
        }}
    ]}
    result, count = _run_renames(bp, 'Product', PRODUCT_MODULE_NAMES, PRODUCT_FIELD_RENAMES, PRODUCT_FLATTENED_OBJECT_FIELDS)
    m = result['flow'][1]['mapper']
    assert m['a'] == '{{50.is_linkable}}', f"selectable not renamed: {m['a']}"
    assert m['b'] == '{{50.is_deleted}}', f"active_flag not renamed: {m['b']}"
    assert m['c'] == '{{50.owner_id}}', f"owner_id.name not flattened: {m['c']}"
    print("[PASS] test_product_renames")


# ========================== DEAL PRODUCT TESTS ==========================

def test_deal_product_renames():
    bp = {"flow": [
        {"id": 60, "module": "pipedrive:listProductsInDealV2", "mapper": {}},
        {"id": 61, "module": "util:Set", "mapper": {
            "a": "{{60.enabled_flag}}", "b": "{{60.last_edit}}"
        }}
    ]}
    result, count = _run_renames(bp, 'DealProduct', DEAL_PRODUCT_MODULE_NAMES, DEAL_PRODUCT_FIELD_RENAMES, DEAL_PRODUCT_FLATTENED_OBJECT_FIELDS)
    m = result['flow'][1]['mapper']
    assert m['a'] == '{{60.is_enabled}}', f"enabled_flag not renamed: {m['a']}"
    assert m['b'] == '{{60.update_time}}', f"last_edit not renamed: {m['b']}"
    print("[PASS] test_deal_product_renames")


# ========================== PIPELINE TESTS ==========================

def test_pipeline_renames():
    bp = {"flow": [
        {"id": 70, "module": "pipedrive:GetPipeline", "mapper": {}},
        {"id": 71, "module": "util:Set", "mapper": {
            "a": "{{70.selected}}", "b": "{{70.active_flag}}", "c": "{{70.deal_probability}}"
        }}
    ]}
    result, count = _run_renames(bp, 'Pipeline', PIPELINE_MODULE_NAMES, PIPELINE_FIELD_RENAMES, PIPELINE_FLATTENED_OBJECT_FIELDS)
    m = result['flow'][1]['mapper']
    assert m['a'] == '{{70.is_selected}}', f"selected not renamed: {m['a']}"
    assert m['b'] == '{{70.is_deleted}}', f"active_flag not renamed: {m['b']}"
    assert m['c'] == '{{70.is_deal_probability_enabled}}', f"deal_probability not renamed: {m['c']}"
    print("[PASS] test_pipeline_renames")


# ========================== STAGE TESTS ==========================

def test_stage_renames():
    bp = {"flow": [
        {"id": 80, "module": "pipedrive:GetStage", "mapper": {}},
        {"id": 81, "module": "util:Set", "mapper": {
            "a": "{{80.rotten_flag}}", "b": "{{80.rotten_days}}", "c": "{{80.active_flag}}"
        }}
    ]}
    result, count = _run_renames(bp, 'Stage', STAGE_MODULE_NAMES, STAGE_FIELD_RENAMES, STAGE_FLATTENED_OBJECT_FIELDS)
    m = result['flow'][1]['mapper']
    assert m['a'] == '{{80.is_deal_rot_enabled}}', f"rotten_flag not renamed: {m['a']}"
    assert m['b'] == '{{80.days_to_rotten}}', f"rotten_days not renamed: {m['b']}"
    assert m['c'] == '{{80.is_deleted}}', f"active_flag not renamed: {m['c']}"
    print("[PASS] test_stage_renames")


# ========================== CROSS-ENTITY ISOLATION ==========================

def test_cross_entity_isolation():
    """Verify entity renames only apply to their own module types."""
    bp = {"flow": [
        {"id": 90, "module": "pipedrive:getDealV2", "mapper": {}},
        {"id": 91, "module": "pipedrive:GetPersonV2", "mapper": {}},
        {"id": 92, "module": "pipedrive:getOrganizationV2", "mapper": {}},
        {"id": 93, "module": "util:Set", "mapper": {
            "deal_phone": "{{90.phone}}",      # NOT a deal rename - stays
            "person_user_id": "{{91.user_id}}", # NOT a person rename - stays
            "org_selectable": "{{92.selectable}}",  # NOT an org rename - stays
            "deal_user_id": "{{90.user_id}}",   # IS a deal rename -> owner_id
            "person_phone": "{{91.phone}}",     # IS a person rename -> phones
            "org_label": "{{92.label}}",        # IS an org rename -> label_ids
        }}
    ]}
    
    blueprint_str = json.dumps(bp)
    for entity_label, module_names, field_renames, flattened_fields in ENTITY_RENAME_CONFIGS:
        entity_ids = find_module_ids_by_names(bp['flow'], module_names)
        if entity_ids:
            blueprint_str, _ = rewrite_entity_field_references(
                blueprint_str, entity_ids, field_renames, flattened_fields, entity_label
            )
    
    result = json.loads(blueprint_str)
    m = result['flow'][3]['mapper']
    
    assert m['deal_phone'] == '{{90.phone}}', f"Deal phone wrongly renamed: {m['deal_phone']}"
    assert m['person_user_id'] == '{{91.user_id}}', f"Person user_id wrongly renamed: {m['person_user_id']}"
    assert m['org_selectable'] == '{{92.selectable}}', f"Org selectable wrongly renamed: {m['org_selectable']}"
    assert m['deal_user_id'] == '{{90.owner_id}}', f"Deal user_id not renamed: {m['deal_user_id']}"
    assert m['person_phone'] == '{{91.phones}}', f"Person phone not renamed: {m['person_phone']}"
    assert m['org_label'] == '{{92.label_ids}}', f"Org label not renamed: {m['org_label']}"
    
    print("[PASS] test_cross_entity_isolation")


if __name__ == "__main__":
    test_deal_simple_renames()
    test_deal_flattened()
    test_deal_no_false_positives()
    test_person_simple_renames()
    test_person_flattened()
    test_org_renames()
    test_activity_renames()
    test_product_renames()
    test_deal_product_renames()
    test_pipeline_renames()
    test_stage_renames()
    test_cross_entity_isolation()
    
    print(f"\n[SUCCESS] All 12 entity field rename tests passed!")
