"""Read-only evidence coverage audit for the general component comparator."""
import collections
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import build_damage  # noqa: E402
import catalog  # noqa: E402
import component_compare  # noqa: E402


def report():
    kinds = collections.Counter(entry.get('kind') for entry in catalog.ENTRIES.values())
    mods = [(key, entry) for key, entry in catalog.ENTRIES.items()
            if entry.get('kind') == 'mod' and not entry.get('family_only')]
    coverage = collections.Counter()
    row_names = collections.Counter()
    selected_levels = collections.Counter()
    exact_main_cards = []
    for identity, _entry in mods:
        for level in range(1, 18):
            resolved = catalog.resolve(identity, level)
            if resolved.get('verified_main_effect'):
                exact_main_cards.append((identity, level))
            status = resolved.get('attribute_coverage') or 'none'
            coverage[status] += 1
            if level == 10:
                selected_levels[status] += 1
            for row in resolved.get('known_attributes') or []:
                row_names[row.get('name') or 'unnamed'] += 1
    modeled_main = [(identity, level) for identity, level in exact_main_cards
                    if f'{identity}:{level}' in component_compare.MAIN_RULES]
    shiny_cards = [identity for identity, _entry in mods
                   if catalog.resolve(identity, 17, shiny=True).get('verified_shiny_main_effect')]
    modeled_shiny = [identity for identity in shiny_cards
                     if f'{identity}:17' in component_compare.MAIN_RULES]
    patterns = {'direct_weapon': r'weapon(?: and status)? dmg|weapon damage',
                'critical': r'crit(?:ical)?(?: dmg| damage| rate| chance)',
                'weakspot': r'weak.?spot',
                'status_elemental': r'status|elemental|power surge|burn|frost|shock',
                'proc_frequency': r'trigger chance|proc chance|trigger rate',
                'firing_cycle': r'reload|magazine|fire rate|ammo',
                'survival': r'shield|damage reduction|heal|hp'}
    mechanic_text = {}
    for category, pattern in patterns.items():
        candidates = [identity for identity, entry in mods
                      if re.search(pattern, str(entry.get('primary_effect') or ''), re.I)]
        modeled = [identity for identity, level in modeled_main if identity in candidates]
        mechanic_text[category] = {'catalog_effect_text_identities': len(candidates),
                                   'exact_main_cards_with_arithmetic': len(modeled)}
    # One photographed value for a variant/attribute/tier can fill several
    # levels. Keep this backlog separate from the much larger level grid.
    tier_needs = set()
    for identity, entry in mods:
        for index, name in enumerate(entry.get('attribute_names') or []):
            plain = re.sub(r' \(aerial bonus\)$', '', name)
            for tier in range(1, 3 if index == 3 else 6):
                if (entry.get('attribute_tier_values') or {}).get(plain, {}).get(str(tier)) is None:
                    tier_needs.add((identity, plain, tier))
    main_families = collections.defaultdict(lambda: {'variants': 0, 'with_effect_text': 0,
                                                       'verified_exact_level_cards': 0})
    verified_identities = {identity for identity, _level in exact_main_cards}
    for identity, entry in mods:
        family = entry.get('tree') or entry.get('name') or identity
        main_families[family]['variants'] += 1
        main_families[family]['with_effect_text'] += bool(entry.get('primary_effect'))
        main_families[family]['verified_exact_level_cards'] += int(identity in verified_identities)
    return {
        'catalog_entries_by_kind': dict(kinds),
        'selectable_mod_variants': len(mods),
        'mod_variant_level_pairs_1_to_17': len(mods) * 17,
        'exact_level_numeric_profile_coverage': dict(coverage),
        'level_10_numeric_profile_coverage': dict(selected_levels),
        'known_attribute_rows_by_name_all_levels': dict(row_names),
        'component_row_names_supported': sorted(component_compare.POOLS),
        'component_row_names_unmodeled': sorted(set(row_names) - set(component_compare.POOLS)),
        'legacy_exact_build_damage_rules': len(build_damage.RULES),
        'main_effect_coverage': {
            'catalog_text_identities': sum(bool(entry.get('primary_effect')) for _identity, entry in mods),
            'exact_level_verified_cards': len(exact_main_cards),
            'exact_level_arithmetic_rules': len(modeled_main),
            'verified_shiny_level_17_cards': len(shiny_cards),
            'shiny_level_17_arithmetic_rules': len(modeled_shiny),
            'unmapped_community_numeric_candidates': catalog.MAGNITUDES['candidate_rows'],
            'source_checked_recording_effects_at_exact_levels': sum(bool(row.get('main_effect_raw')) for row in catalog.REVIEWED['entries'].values()),
            'note': 'Community candidate magnitudes lack an exact Field Guide level and are not promoted to calculations.'},
        'main_effect_text_categories': mechanic_text,
        'evidence_backlog': {'families': len(main_families),
                             'identities_with_known_attribute_names': sum(bool(entry.get('attribute_names')) for _identity, entry in mods),
                             'missing_variant_attribute_tier_values': len(tier_needs),
                             'missing_by_attribute': dict(collections.Counter(name for _identity, name, _tier in tier_needs).most_common()),
                             'known_shared_tier_candidates_not_applied': len(catalog.SHARED_TIERS),
                             'family_variant_counts': dict(sorted(main_families.items()))},
        'official_set_rules': {'total': len(component_compare.SET_RULES),
                               'numeric_damage_thresholds_modeled': sum(rule.get('bonus_fraction') is not None for rule in component_compare.SET_RULES)},
        'official_armor_rules': {'cataloged': sum(rule.get('system') == 'armor' for rule in json.loads((ROOT / 'rules.json').read_text())['rules']),
                                 'numeric_keyword_operator_modeled': 1,
                                 'triggered_effect_repeat_operator_modeled': 1},
        'reviewed_recording_profile_overlay': {
            'exact_profiles': len(catalog.REVIEWED['entries']),
            'complete_numeric': sum(all(attr.get('value_percent') is not None for attr in row['attributes'])
                                    for row in catalog.REVIEWED['entries'].values()),
            'partial_numeric': sum(any(attr.get('value_percent') is None for attr in row['attributes'])
                                   for row in catalog.REVIEWED['entries'].values()),
            'conflicts_held': len(catalog.REVIEWED['conflicts']),
            'note': 'Exact source-checked Top observations only; not ownership or current equip. One complete profile overlaps static evidence.'},
        'denominator_note': '985 catalog mod entries include one family-only nonselectable record; 984 selectable variants times 17 levels is 16,728 theoretical pairs.',
        'note': 'Numeric profile coverage and component mapping are separate from verified main-effect, stacking, set, weapon proc and encounter mechanics. No all-catalog DPS claim follows from these counts.'
    }


if __name__ == '__main__':
    print(json.dumps(report(), indent=2, sort_keys=True))
