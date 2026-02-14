"""
Test structural v2 fixes: visible_to, start, sort handling
in native module mappers.
"""
import json
from migrate_pipedrive import upgrade_pipedrive_connection


def make_test_module(module_name, mapper, module_id=100):
    """Create a minimal module for testing upgrade_pipedrive_connection."""
    return {
        "id": module_id,
        "module": module_name,
        "version": 1,
        "mapper": mapper,
        "metadata": {
            "expect": [],
            "restore": {},
            "interface": []
        },
        "parameters": {
            "__IMTCONN__": 12345
        }
    }


def test_visible_to_string_to_int():
    """visible_to should be converted from string to int in native modules."""
    module = make_test_module("pipedrive:UpdateDeal", {
        "title": "Test Deal",
        "visible_to": "3"
    })
    result = upgrade_pipedrive_connection(module, "test.json", override_connection_id=99999)
    assert result == True
    mapper = module.get('mapper', {})
    assert mapper.get('visible_to') == 3, f"visible_to should be 3 (int), got {mapper.get('visible_to')}"
    print("[PASS] test_visible_to_string_to_int")


def test_visible_to_dynamic_unchanged():
    """visible_to with a dynamic value (formula) should pass through unchanged."""
    module = make_test_module("pipedrive:UpdateDeal", {
        "title": "Test Deal",
        "visible_to": "{{5.visible_to}}"
    })
    result = upgrade_pipedrive_connection(module, "test.json", override_connection_id=99999)
    assert result == True
    mapper = module.get('mapper', {})
    # Dynamic formula is not a digit string, so it should stay as-is
    assert mapper.get('visible_to') == "{{5.visible_to}}", f"Dynamic visible_to should be unchanged, got {mapper.get('visible_to')}"
    print("[PASS] test_visible_to_dynamic_unchanged")


def test_start_removed():
    """'start' pagination param should be removed from native module mappers."""
    module = make_test_module("pipedrive:ListDeals", {
        "limit": 50,
        "start": 100
    })
    result = upgrade_pipedrive_connection(module, "test.json", override_connection_id=99999)
    assert result == True
    mapper = module.get('mapper', {})
    assert 'start' not in mapper, f"'start' should be removed, mapper has: {list(mapper.keys())}"
    assert mapper.get('limit') == 50, f"'limit' should be preserved"
    print("[PASS] test_start_removed")


def test_sort_split():
    """'sort' should be split into sort_by and sort_direction."""
    module = make_test_module("pipedrive:ListDeals", {
        "limit": 50,
        "sort": "add_time DESC"
    })
    result = upgrade_pipedrive_connection(module, "test.json", override_connection_id=99999)
    assert result == True
    mapper = module.get('mapper', {})
    assert 'sort' not in mapper, f"'sort' should be removed, mapper has: {list(mapper.keys())}"
    assert mapper.get('sort_by') == 'add_time', f"sort_by should be 'add_time', got {mapper.get('sort_by')}"
    assert mapper.get('sort_direction') == 'desc', f"sort_direction should be 'desc', got {mapper.get('sort_direction')}"
    print("[PASS] test_sort_split")


def test_sort_no_direction():
    """'sort' without direction should default to 'asc'."""
    module = make_test_module("pipedrive:ListDeals", {
        "sort": "title"
    })
    result = upgrade_pipedrive_connection(module, "test.json", override_connection_id=99999)
    assert result == True
    mapper = module.get('mapper', {})
    assert mapper.get('sort_by') == 'title', f"sort_by should be 'title', got {mapper.get('sort_by')}"
    assert mapper.get('sort_direction') == 'asc', f"sort_direction should default to 'asc', got {mapper.get('sort_direction')}"
    print("[PASS] test_sort_no_direction")


def test_combined_fixes():
    """All fixes should work together on the same module."""
    module = make_test_module("pipedrive:ListDeals", {
        "visible_to": "1",
        "start": 200,
        "sort": "update_time ASC",
        "limit": 100
    })
    result = upgrade_pipedrive_connection(module, "test.json", override_connection_id=99999)
    assert result == True
    mapper = module.get('mapper', {})
    assert mapper.get('visible_to') == 1, f"visible_to should be 1, got {mapper.get('visible_to')}"
    assert 'start' not in mapper, "'start' should be removed"
    assert mapper.get('sort_by') == 'update_time', f"sort_by wrong: {mapper.get('sort_by')}"
    assert mapper.get('sort_direction') == 'asc', f"sort_direction wrong: {mapper.get('sort_direction')}"
    assert mapper.get('limit') == 100, "'limit' should be preserved"
    print("[PASS] test_combined_fixes")


if __name__ == "__main__":
    test_visible_to_string_to_int()
    test_visible_to_dynamic_unchanged()
    test_start_removed()
    test_sort_split()
    test_sort_no_direction()
    test_combined_fixes()
    
    print(f"\n[SUCCESS] All 6 structural v2 fix tests passed!")
