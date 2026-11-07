"""Public mod detail projection, independent of inventory and Field Guide state."""
from __future__ import annotations

import json
import hashlib
import re
from pathlib import Path

import catalog
import native_mod_identity
import native_mod_frame_catalog
import native_mod_main_effect
import published_bonus_lines
import public_semantic_crosscheck


PUBLIC_CORE = json.loads((Path(__file__).with_name('evidence_packets') /
                          'public-core-identity-v1.json').read_text())['entries']
_CONFLICT_PATH = Path(__file__).with_name('evidence_packets') / 'native-published-layout-conflicts-v1.json'
_CONFLICT_SHA = 'e037b05436f8f317e326cb4e2d17c95cffbb0e72943c3efd3ed40f4f48e8aba8'
if hashlib.sha256(_CONFLICT_PATH.read_bytes()).hexdigest() != _CONFLICT_SHA:
    raise ValueError('Exact native/published conflict packet hash mismatch')
_CONFLICT_PACKET = json.loads(_CONFLICT_PATH.read_text())
if (_CONFLICT_PACKET.get('source_build') != '26267212' or
        _CONFLICT_PACKET.get('native_frame_packet_sha256') !=
        native_mod_frame_catalog.HASHES[native_mod_frame_catalog.PACKET.name] or
        _CONFLICT_PACKET.get('native_catalog_sha256') !=
        hashlib.sha256(Path(__file__).with_name('catalog_systems.json').read_bytes()).hexdigest()):
    raise ValueError('Exact native/published conflict source mismatch')
_CONFLICT_IDENTITIES = {row['catalog_id']: row for row in _CONFLICT_PACKET['identities']}
if len(_CONFLICT_IDENTITIES) != 2:
    raise ValueError('Exact native/published conflict identity count mismatch')


def low_hp_maximum(row):
    """Return only the sourced Lunar maximum, never an inferred HP curve."""
    if (row.get('source_conflict') or row.get('value_percent') is not None or
            not str(row.get('stat_type') or row.get('formula_key') or '').startswith('lunar_') or
            'low hp' not in str(row.get('condition') or '').lower()):
        return None
    value = (row.get('components') or {}).get('max_bonus_percent')
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 1000:
        return None
    return float(value)


def _display_value(row):
    components = row.get('components') or {}
    if components.get('max_bonus_percent') is not None:
        return f"up to +{components['max_bonus_percent']:g}%"
    if components.get('base_percent') is not None:
        base = f"+{components['base_percent']:g}%"
        extra = next((components[key] for key in ('shield_extra_max_percent',
                      'elevation_extra_max_percent', 'behind_extra_percent')
                      if components.get(key) is not None), None)
        if extra is not None:
            return f'{base}; up to +{extra:g}% conditional extra'
    if components.get('per_stack_percent') is not None:
        return (f"+{components['per_stack_percent']:g}% per stack; "
                f"max {components.get('max_stacks', '?')} stacks")
    return None


def _line(position, tier, raw):
    row = raw or {}
    locked = tier == 0
    value = row.get('value_percent') if not locked else None
    return {'position': position, 'name': row.get('name') or f'Bonus line {position}',
            'raw_text': None if locked else row.get('raw_text'),
            'stat_type': row.get('stat_type'), 'tier': tier, 'locked': locked,
            'value_percent': value, 'unit': row.get('unit') or 'percent',
            'direction': row.get('direction') or 'unknown',
            'condition': row.get('condition'),
            'conditional_bonus_percent': row.get('conditional_bonus_percent'),
            'display_value': None if locked else _display_value(row),
            'status': ('locked_at_this_level' if locked else
                       'source_conflict' if row.get('source_conflict') or row.get('conflict') else
                       'observed_value_published_conflict' if row.get('published_layout_conflict') and value is not None else
                       'published_layout_conflict' if row.get('published_layout_conflict') else
                       (row.get('public_status') or
                        ('value_available' if value is not None else 'value_unavailable'))),
            'source_ref': row.get('source'),
            'layout_source_ref': row.get('layout_source_ref'),
            'source_status': row.get('source_status'),
            'source_sha256': row.get('source_sha256'),
            'formula_key': row.get('formula_key'),
            'components': row.get('components'),
            'native_attribute': row.get('native_attribute'),
            'native_entry_no': row.get('native_entry_no'),
            'native_entry_level': row.get('native_entry_level'),
            'native_row_literal_offset': row.get('native_row_literal_offset'),
            'native_duration_seconds': row.get('native_duration_seconds'),
            'native_cooldown_seconds': row.get('native_cooldown_seconds'),
            'native_corroboration': row.get('native_corroboration'),
            'native_graph_review_status': row.get('native_graph_review_status'),
            'native_heal_input_configuration': row.get('native_heal_input_configuration'),
            'native_configured_candidate': row.get('native_configured_candidate'),
            'native_candidate_source_sha256': row.get('native_candidate_source_sha256'),
            'native_generic_catalog_only': bool(row.get('native_generic_catalog_only')),
            'calculation_exclusion_reason': row.get('calculation_exclusion_reason'),
            'recorded_english_label': row.get('recorded_english_label'),
            'recorded_source': row.get('recorded_source'),
            'installed_english_label': row.get('installed_english_label'),
            'native_meaning': row.get('native_meaning'),
            'source_warning': row.get('source_warning'),
            'source_conflict': bool(row.get('source_conflict') or row.get('conflict')),
            'published_layout_conflict': bool(row.get('published_layout_conflict')),
            'published_conflict_reasons': row.get('published_conflict_reasons') or []}


def _public_rows(catalog_id, level, observed):
    if catalog_id == 'mod:pants_mod:precision-charge-aero' and not observed.get('shiny'):
        return _aero_native_rows(level, observed)
    if catalog_id in native_mod_identity.TWO_FRAME_IDENTITIES:
        return _two_frame_native_rows(catalog_id, level, observed)
    published = published_bonus_lines.profile(catalog_id, level,
                                               shiny=observed.get('shiny') is True)
    candidate_rows = published['lines'] if published['status'] != 'blocked' else []
    source_rows = observed.get('known_attributes') or []
    layout_conflicts = public_semantic_crosscheck.layout_conflicts(
        catalog_id, observed.get('shiny') is True)
    merged = []
    for index in range(4):
        source = source_rows[index] if index < len(source_rows) else {}
        candidate = candidate_rows[index] if index < len(candidate_rows) else {}
        semantic = layout_conflicts.get(index) or []
        if source.get('value_percent') is not None and not source.get('source_conflict'):
            row = dict(source)
            row['source_status'] = row.get('source_status') or 'held_exact_identity_tier_value'
            if candidate.get('value_percent') is not None:
                if semantic or abs(abs(row['value_percent']) - abs(candidate['value_percent'])) > 1e-6:
                    row.update(published_layout_conflict=True,
                               published_conflict_reasons=sorted({reason for detail in semantic
                                                                  for reason in detail['reasons']}) or ['magnitude'],
                               published_candidate=candidate)
                else:
                    row['published_corroboration'] = candidate['source_ref']
            elif (candidate.get('components') and not semantic and
                  str(candidate.get('stat_type') or '').startswith('resonance_')):
                row.update(stat_type=candidate['stat_type'],
                           components=candidate['components'],
                           published_structured_corroboration=candidate['source_ref'])
            merged.append(row)
        elif source.get('source_conflict') or source.get('direction') == 'ambiguous':
            merged.append({**source, 'published_candidate': candidate,
                           'source_conflict': True})
        elif semantic and candidate:
            def common(field):
                values = {detail.get(field) for detail in semantic}
                return next(iter(values)) if len(values) == 1 else None
            held_name = source.get('name') or common('observed_name')
            held_condition = source.get('condition') or common('observed_condition')
            merged.append({**source, 'name': held_name or f'Bonus line {index + 1}',
                           'condition': held_condition,
                           'unit': source.get('unit') or common('observed_unit') or 'percent',
                           'source': source.get('source') or common('observed_source'),
                           'source_status': source.get('source_status') or
                                            'held_identity_layout_at_other_level',
                           'value_percent': None,
                           'published_layout_conflict': True,
                           'published_conflict_reasons': sorted({reason for detail in semantic
                                                                  for reason in detail['reasons']}),
                           'published_candidate': candidate})
        elif candidate.get('value_percent') is not None:
            components = candidate['components']
            merged.append({'name': candidate['name'], 'stat_type': candidate['stat_type'],
                           'value_percent': candidate['value_percent'],
                           'condition': candidate.get('condition'),
                           'conditional_bonus_percent': (components.get('aerial_extra_percent')
                                                         if candidate['stat_type'].startswith('aero_') else None),
                           'components': components,
                           'formula_key': candidate['stat_type'],
                           'source': candidate['source_ref'],
                           'layout_source_ref': candidate['layout_source_ref'],
                           'source_status': candidate['source_status'],
                           'public_status': candidate['status'],
                           'unit': 'percent',
                           'direction': ('decrease' if candidate['value_percent'] < 0 else 'increase')})
        elif candidate.get('components'):
            merged.append({'name': candidate['name'], 'stat_type': candidate['stat_type'],
                           'value_percent': None, 'condition': candidate.get('condition'),
                           'components': candidate['components'],
                           'formula_key': candidate['stat_type'],
                           'source': candidate['source_ref'],
                           'layout_source_ref': candidate['layout_source_ref'],
                           'source_status': candidate['source_status'],
                           'public_status': candidate['status'],
                           'unit': 'percent', 'direction': 'unknown'})
        else:
            merged.append(source or candidate)
    return merged, published


def _verified_frame_native_rows(catalog_id, level, observed, native):
    """Configured native text, with exact held cards and conflicts kept separate."""
    conflicts = native_mod_frame_catalog.exact_record_conflicts(
        catalog_id, shiny=observed.get('shiny') is True)
    source_rows = observed.get('known_attributes') or []
    tiers = observed['level_profile']
    rows = []
    for index, line in enumerate(native['ordered_lines']):
        locked = line['state'] == 'locked'
        if locked != (tiers[index] == 0):
            raise ValueError('Native frame unlock state conflicts with catalog level chart')
        recorded = source_rows[index] if index < len(source_rows) else {}
        exact_recorded = (not locked and recorded.get('observed_level') == level and
                          'Field Guide frame' in str(recorded.get('source_status') or ''))
        if index in conflicts:
            row = dict(recorded) if exact_recorded else {
                'name': recorded.get('name') or f'Bonus line {index + 1}',
                'value_percent': None,
                'unit': 'percent',
            }
            row.update(source_conflict=True,
                       source_warning='Native configured wording conflicts with a held exact card for this identity; unobserved values withheld.',
                       native_configured_candidate=line.get('text'),
                       native_generic_catalog_only=not exact_recorded)
        elif locked:
            row = {'name': recorded.get('name') or f'Bonus line {index + 1}',
                   'value_percent': None, 'unit': 'percent'}
        else:
            direct = line['kind'] == 'direct_affix'
            row = {'name': line['text'], 'raw_text': line['text'],
                   'value_percent': round(line['configured_fraction'] * 100, 9) if direct else None,
                   'unit': 'percent', 'direction': 'unknown',
                   'native_attribute': line.get('native_attr_id') or line.get('native_attributes'),
                   'native_entry_no': line['entry_no'],
                   'native_entry_level': line['entry_level'],
                   'native_row_literal_offset': line['entry_row_literal_offset'],
                   'native_generic_catalog_only': True,
                   'native_graph_review_status': line.get('graph_review_status') or line.get('attribute_status'),
                   'native_heal_input_configuration': line.get('configured_heal_input'),
                   'calculation_exclusion_reason': 'Configured native catalog line; selected roll and server application are unverified',
                   'native_corroboration': {'status': 'native_config_only',
                                            'effect_activated': False,
                                            'attribute_status': line.get('attribute_status')},
                   'source_warning': ('Native source means damage to all monsters; installed English wording differs. Target application is unverified.'
                                      if line.get('text_status') == 'native_source_faithful_override' else None)}
            if exact_recorded:
                row['recorded_english_label'] = recorded.get('name')
                row['recorded_source'] = recorded.get('source')
                row['native_corroboration']['status'] = 'recorded_card_text_agrees'
        if exact_recorded and index in conflicts:
            row['native_candidate_source_sha256'] = native['source_sha256']
            row['public_status'] = 'observed_value_native_conflict'
        else:
            row.update(source='evidence_packets/native-verified-mod-frame-catalog-v1.md',
                       source_sha256=native['source_sha256'],
                       source_status='native_catalog_configuration_runtime_unverified',
                       public_status='exact_native_catalog_configuration')
        row.update(native_frame_code=native['native_frame_code'],
                   native_item_no=native['native_item_no'],
                   native_mod_code=native['native_mod_code'])
        rows.append(row)
    return rows, {'status': 'exact_native_catalog_configuration',
                  'alias_status': None, 'alias_source_urls': [],
                  'shiny_suffix_scope': 'exact_shared_native_frame' if observed.get('shiny') else None,
                  'shiny_availability_for_identity': bool(observed.get('shiny')),
                  'shiny_core_effect_status': 'separate_buff_not_inferred' if observed.get('shiny') else None,
                  'reason': None}


def _aero_native_rows(level, observed):
    """Use exact native catalog configuration without claiming runtime activation."""
    native = native_mod_identity.aero_four_line_preview(level)
    source_rows = observed.get('known_attributes') or []
    tiers = observed['level_profile']
    rows = []
    for index, line in enumerate(native['ordered_lines']):
        if bool(line['locked']) != (tiers[index] == 0):
            raise ValueError('Aero native unlock state conflicts with the catalog level chart')
        recorded = source_rows[index] if index < len(source_rows) else {}
        exact_recorded = (not line['locked'] and
                          recorded.get('observed_level') == level and
                          recorded.get('source_status') == 'visually checked current Field Guide frame')
        value = line['value_percent']
        extra = line['conditional_bonus_percent']
        conflict = bool(exact_recorded and recorded.get('value_percent') is not None and
                        (abs(recorded['value_percent'] - value) > 1e-6 or
                         recorded.get('conditional_bonus_percent') != extra))
        row = {'name': line['name'], 'value_percent': None if conflict else value,
               'conditional_bonus_percent': None if conflict else extra,
               'condition': 'aerial hit for extra component' if index in (0, 1) and not line['locked'] else None,
               'stat_type': ('native_E42_remote', 'native_E02_crit',
                             'native_monster_type_damage', 'native_A02_max_hp')[index],
               'native_attribute': line['native_attribute'],
               'native_entry_no': line['entry_no'],
               'native_entry_level': line['entry_level'],
               'native_row_literal_offset': line['source_row_literal_offset'],
               'source': 'evidence_packets/native-aero-four-lines-v1.md',
               'source_sha256': native['source_sha256']['native-aero-four-lines-v1.json'],
               'source_status': 'native_catalog_configuration_runtime_unverified',
               'public_status': 'exact_native_catalog_configuration',
               'unit': 'percent', 'direction': 'increase',
               'recorded_english_label': recorded.get('name') if exact_recorded else None,
               'recorded_source': recorded.get('source') if exact_recorded else None,
               'native_meaning': line['name'],
               'installed_english_label': line.get('installed_english_label'),
               'source_warning': line.get('source_warning') if not line['locked'] else None,
               'source_conflict': conflict,
               'native_corroboration': {'status': 'numeric_agrees_label_differs' if index == 2 and exact_recorded and recorded.get('value_percent') is not None and not conflict else
                                       'recorded_card_value_agrees' if exact_recorded and recorded.get('value_percent') is not None and not conflict else
                                       'recorded_card_value_conflict' if conflict else 'native_config_only',
                                       'property_id': line['native_attribute'],
                                       'entry_level': line['entry_level'],
                                       'effect_activated': False}}
        rows.append(row)
    return rows, {'status': 'exact_native_catalog_configuration',
                  'alias_status': None, 'alias_source_urls': [],
                  'shiny_suffix_scope': None, 'shiny_availability_for_identity': None,
                  'shiny_core_effect_status': None, 'reason': None}


def _two_frame_native_rows(catalog_id, level, observed):
    """Four sourced catalog lines; no owned or server-active buff inference."""
    native = native_mod_identity.two_frame_preview(catalog_id, level,
                                                  shiny=observed.get('shiny') is True)
    shock = catalog_id == 'mod:weapon_mod:shock-diffusion-survival'
    names = (('Max HP', 'Damage reduction after taking damage',
              'Damage from monsters received', 'Damage to all monsters') if shock else
             ('Shrapnel DMG', 'Shrapnel Crit DMG', 'Shrapnel Weakspot DMG',
              'Damage to all monsters'))
    source_rows = observed.get('known_attributes') or []
    rows = []
    for index, line in enumerate(native['ordered_lines']):
        if bool(line['state'] == 'locked') != (observed['level_profile'][index] == 0):
            raise ValueError('Native frame unlock state conflicts with catalog chart')
        recorded = source_rows[index] if index < len(source_rows) else {}
        exact_recorded = (line['state'] == 'configured' and
                          recorded.get('observed_level') == level and
                          recorded.get('source_status') == 'visually checked current Field Guide frame')
        values = ([line['display_percent']] if line.get('display_percent') is not None else
                  line.get('display_values') or [])
        value = float(values[0]) if values else None
        conflict = bool(exact_recorded and recorded.get('value_percent') is not None and
                        abs(recorded['value_percent'] - value) > 1e-6)
        row = {'name': names[index], 'value_percent': None if conflict else value,
               'unit': 'percent',
               'direction': 'reduction' if shock and index in (1, 2) else 'increase',
               'condition': ('after taking damage; lasts 3 seconds; 6-second cooldown'
                             if shock and index == 1 and line['state'] == 'configured' else None),
               'native_duration_seconds': float(values[1]) if shock and index == 1 and len(values) > 1 else None,
               'native_cooldown_seconds': float(values[2]) if shock and index == 1 and len(values) > 2 else None,
               'stat_type': ('native_max_hp', 'native_on_hit_reduction',
                             'native_monster_reduction', 'native_monster_type_damage')[index]
                            if shock else ('native_shrapnel_damage', 'native_shrapnel_crit',
                                           'native_shrapnel_weakspot', 'native_monster_type_damage')[index],
               'native_attribute': line.get('native_attr_id') or line.get('native_attributes'),
               'native_entry_no': line['entry_no'], 'native_entry_level': line['entry_level'],
               'native_row_literal_offset': line.get('entry_row_literal_offset'),
               'source': 'evidence_packets/native-two-frame-levels-v1.md',
               'source_sha256': native['source_sha256']['native-two-frame-levels-v1.json'],
               'source_status': 'native_catalog_configuration_runtime_unverified',
               'public_status': 'exact_native_catalog_configuration',
               'recorded_english_label': recorded.get('name') if exact_recorded else None,
               'recorded_source': recorded.get('source') if exact_recorded else None,
               'source_warning': ('Native source means damage to all monsters; installed English wording differs. Target application is unverified.'
                                  if index == 3 and line['state'] == 'configured' else None),
               'source_conflict': conflict,
               'native_corroboration': {'status': 'numeric_agrees_label_differs' if index == 3 and exact_recorded and not conflict else
                                        'recorded_card_value_agrees' if exact_recorded and not conflict else
                                        'recorded_card_value_conflict' if conflict else 'native_config_only',
                                        'effect_activated': False}}
        rows.append(row)
    return rows, {'status': 'exact_native_catalog_configuration', 'alias_status': None,
                  'alias_source_urls': [], 'shiny_suffix_scope': None,
                  'shiny_availability_for_identity': None, 'shiny_core_effect_status': None,
                  'reason': None}


def calculation_rows(catalog_id, level, *, shiny=False, resolved=None):
    """Expose sourced line rows to model paths without changing catalog truth."""
    if resolved is None:
        resolved = catalog.resolve(catalog_id, level, shiny=shiny)
    if resolved['entry']['kind'] != 'mod' or not 1 <= level <= 17:
        raise ValueError('Calculation rows need an exact mod and level')
    rows, published = _public_rows(catalog_id, level, resolved)
    conflict = _CONFLICT_IDENTITIES.get(catalog_id) if not shiny else None
    native_scope_candidate = not shiny and any(
        row.get('name') in ('Damage against enemies', 'All DMG Boost') and
        row.get('value_percent') is not None and
        str(row.get('source_status') or '').startswith('published_formula_candidate')
        for row in rows)
    native = (native_mod_frame_catalog.preview(catalog_id, level, shiny=False)
              if conflict or native_scope_candidate else None)
    if conflict and (native is None or native['native_item_no'] != conflict['normal_native_item_id']):
        raise ValueError('Exact native conflict item identity mismatch')
    native_lines = native['ordered_lines'] if native is not None else None
    tiers = resolved['level_profile']
    selected = []
    for index, (row, tier) in enumerate(zip(rows, tiers)):
        if tier == 0:
            continue
        # A published scalar model cannot stand in for a different native
        # configured line at the same position. Keep exact held observations
        # separate; this guard only removes contradicted community candidates.
        if (native_lines is not None and index < len(native_lines) and
                str(row.get('source_status') or '').startswith('published_formula_candidate') and
                row.get('value_percent') is not None and
                not str(row.get('stat_type') or '').startswith('resonance_')):
            configured = native_lines[index]
            text = str(configured.get('text') or '').strip()
            match = re.fullmatch(r'(.+?)\s*([+\-])\s*(\d+(?:\.\d+)?)%', text)
            same_name = bool(match and re.sub(r'\s+', ' ', match.group(1)).strip().casefold() ==
                             re.sub(r'\s+', ' ', str(row.get('name') or '')).strip().casefold())
            same_value = bool(match and abs((1 if match.group(2) == '+' else -1) *
                                             float(match.group(3)) - row['value_percent']) < 1e-9)
            native_monster_scope = (row.get('name') == 'Damage against enemies' and
                                    bool(re.fullmatch(r'Damage to all monsters \+\d+(?:\.\d+)?%', text)) and
                                    configured.get('kind') == 'buff_text' and
                                    {item['attr_id'] for item in configured.get('native_attributes') or []} ==
                                    {'E99', 'E100', 'E101', 'E102'})
            native_general_scope = (index == 0 and native['native_frame_code'] == 0 and
                                    row.get('name') == 'All DMG Boost' and
                                    bool(re.fullmatch(r'DMG \+\d+(?:\.\d+)?%', text)) and
                                    configured.get('kind') == 'buff_text' and
                                    {item['attr_id'] for item in configured.get('native_attributes') or []} ==
                                    {'E42', 'E43'})
            if (native_monster_scope or native_general_scope or
                    conflict and not (same_name and same_value and not row.get('condition'))):
                reason = ('native_monster_scope_not_published_enemy_scope' if native_monster_scope else
                          'native_remote_dot_scope_not_all_damage' if native_general_scope and not conflict else
                          'native_configured_line_identity_or_value')
                row = {**row, 'value_percent': None, 'components': None,
                       'conditional_bonus_percent': None,
                       'source_conflict': True,
                       'published_layout_conflict': True,
                       'published_conflict_reasons': [reason],
                       'native_configured_candidate': text,
                       'native_candidate_source_sha256': native['source_sha256'],
                       'calculation_exclusion_reason':
                       ('Native configured bonus targets four monster classes, not an established generic enemy filter; current damage contribution withheld'
                        if native_monster_scope else
                        'Native General bonus targets remote and damage-over-time properties, not an established all-damage bucket; current damage contribution withheld'
                        if native_general_scope and not conflict else
                        'Published scalar line differs from this exact native configured position; current damage contribution withheld')}
        if row.get('native_generic_catalog_only'):
            row = {**row, 'value_percent': None, 'components': None,
                   'calculation_exclusion_reason': row.get('calculation_exclusion_reason') or
                   'Native catalog configuration has no proven selected-roll/server activation'}
        if ((catalog_id == 'mod:pants_mod:precision-charge-aero' and not shiny and index == 2) or
                (catalog_id in native_mod_identity.TWO_FRAME_IDENTITIES and index == 3)):
            row = {**row, 'value_percent': None,
                   'calculation_exclusion_reason': 'Native monster-type properties are not generic All DMG Boost or an established target filter'}
        selected.append({**row, 'tier': tier,
                         'source': row.get('source') or row.get('layout_source_ref'),
                         'source_status': row.get('source_status') or published['status'],
                         'public_bonus_position': index + 1})
    numeric = ('complete' if all(row.get('value_percent') is not None for row in selected)
               else 'partial' if selected else 'none')
    if any(str(row.get('source_status') or '').startswith('published_formula_candidate') or
           (row.get('published_layout_conflict') and row.get('value_percent') is None and
            not row.get('source_conflict'))
           for row in selected):
        numeric = 'published_candidate_' + numeric
    return selected, numeric, published['status']


def detail(catalog_id, level=None, *, shiny=False):
    entry = catalog.ENTRIES.get(catalog_id)
    if not entry or entry.get('kind') != 'mod' or entry.get('family_only'):
        raise ValueError('Choose an exact selectable mod identity')
    if not isinstance(shiny, bool):
        raise ValueError('Shiny selection must be true or false')
    if level is None:
        level = 17
    if isinstance(level, bool) or not isinstance(level, int) or not 1 <= level <= 17:
        raise ValueError('Preview level must be a whole number from 1 to 17')
    if shiny and level != 17:
        raise ValueError('Shiny preview requires level 17')
    legacy_only = entry.get('system_generation') == 'legacy_random_roll' and not entry.get('current_records')
    if legacy_only:
        return {'catalog_id': catalog_id, 'display_name': entry.get('display_name') or entry['name'],
                'slot': entry['slot'], 'variant': entry.get('variant'),
                'system_scope': 'legacy_instance_specific', 'preview_level': None,
                'shiny': False, 'core_effect': {'text': entry.get('primary_effect'),
                                               'source_ref': entry.get('source_url'),
                                               'status': 'historical_or_instance_specific'},
                'bonus_lines': [], 'progression': [],
                'missing': ['Legacy instance rolls cannot be derived from the current Field Guide level chart.']}
    progression = []
    selected_published = None
    for candidate_level in range(1, 18):
        current_shiny = shiny and candidate_level == 17
        resolved = catalog.resolve(catalog_id, candidate_level, shiny=current_shiny)
        tiers = resolved['level_profile']
        rows, published = _public_rows(catalog_id, candidate_level, resolved)
        names = resolved.get('known_attribute_names') or entry.get('attribute_names') or []
        lines = [_line(index + 1, tier,
                       rows[index] if index < len(rows) else
                       {'name': names[index]} if index < len(names) else None)
                 for index, tier in enumerate(tiers)]
        progression.append({'level': candidate_level, 'shiny': current_shiny,
                            'bonus_lines': lines,
                            'known_numeric_lines': sum(row['value_percent'] is not None for row in lines)})
        if candidate_level == level:
            selected_published = published
    selected = progression[level - 1]
    configured_progression = []
    if native_mod_frame_catalog.exact_identity(catalog_id, shiny=shiny) is not None:
        for candidate_level in range(1, 18):
            current_shiny = shiny and candidate_level == 17
            native = native_mod_frame_catalog.preview(catalog_id, candidate_level,
                                                      shiny=current_shiny)
            if native is None:
                continue
            candidate_resolved = catalog.resolve(catalog_id, candidate_level,
                                                 shiny=current_shiny)
            native_rows, _ = _verified_frame_native_rows(
                catalog_id, candidate_level, candidate_resolved, native)
            configured_progression.append({
                'level': candidate_level, 'shiny': current_shiny,
                'bonus_lines': [_line(index + 1, tier, native_rows[index])
                                for index, tier in enumerate(candidate_resolved['level_profile'])],
            })
    configured_selected = next((row for row in configured_progression
                                if row['level'] == level), None)
    resolved = catalog.resolve(catalog_id, level, shiny=shiny)
    public_core = PUBLIC_CORE.get(catalog_id)
    if public_core and any(entry.get(key) != public_core['exact_' + key]
                           for key in ('name', 'slot', 'variant')):
        raise ValueError('Public core source identity mismatch: ' + catalog_id)
    effect_candidates = (resolved.get('effect_candidates') or
                         (public_core or {}).get('detail_effect_variants') or [])
    core = resolved.get('verified_shiny_main_effect' if shiny else 'verified_main_effect')
    if isinstance(core, dict):
        core_text = core.get('text') or resolved.get('primary_effect')
        core_source = core.get('source') or entry.get('source_url')
        core_status = 'exact_level_source'
    else:
        core_text = (None if shiny else resolved.get('primary_effect'))
        core_source = entry.get('source_url') or (public_core or {}).get('source_url')
        core_status = ('shiny_core_effect_unverified' if shiny else
                       'source_conflict' if entry.get('effect_text_conflict') else
                       'catalog_text_level_strength_unconfirmed' if core_text else
                       'published_variants_level_unmapped' if effect_candidates else
                       'effect_text_unavailable')
    # The public detail pages often list old effect ranks without a mapping to
    # the 2026 Field Guide's seventeen levels. Keep the exact page text visible,
    # but never select a rank as the effect for the requested level.
    variant_source = (entry.get('detail_source_urls') or
                      (public_core or {}).get('detail_source_urls') or [core_source])[0]
    unbound_variants = ([{'text': text, 'source_ref': variant_source}
                         for text in effect_candidates]
                        if not core_text and not shiny else [])
    if unbound_variants:
        core_source = variant_source
    candidate_conflicts = []
    if not shiny and (catalog_id in _CONFLICT_IDENTITIES or any(
            row['name'] in ('Damage against enemies', 'All DMG Boost') and
            row['value_percent'] is not None and
            str(row.get('source_status') or '').startswith('published_formula_candidate')
            for row in selected['bonus_lines'])):
        calculation, _, _ = calculation_rows(catalog_id, level, shiny=False,
                                             resolved=resolved)
        for row in calculation:
            if not set(row.get('published_conflict_reasons') or []) & {
                    'native_configured_line_identity_or_value',
                    'native_monster_scope_not_published_enemy_scope',
                    'native_remote_dot_scope_not_all_damage'}:
                continue
            position = row['public_bonus_position']
            candidate = selected['bonus_lines'][position - 1]
            candidate_conflicts.append({
                'position': position,
                'published_name': candidate['name'],
                'published_value_percent': candidate['value_percent'],
                'published_source_ref': candidate['source_ref'],
                'native_configured_text': row['native_configured_candidate'],
                'native_source_sha256': row['native_candidate_source_sha256'],
                'calculation_status': 'excluded_native_source_conflict',
            })
    return {'catalog_id': catalog_id, 'display_name': entry.get('display_name') or entry['name'],
            'slot': entry['slot'], 'variant': entry.get('variant'),
            'system_scope': ('current_field_guide' if entry.get('current_records') or
                             entry.get('system_generation') == 'current_field_guide' else
                             'current_candidate_variant_unverified'),
            'preview_level': level, 'shiny': shiny,
            'core_effect': {'text': core_text, 'source_ref': core_source,
                            'status': core_status, 'conflict': bool(entry.get('effect_text_conflict')),
                            'unbound_variants': unbound_variants},
            'native_main_effect': native_mod_main_effect.for_catalog(catalog_id, shiny=shiny),
            'bonus_lines': selected['bonus_lines'], 'progression': progression,
            'published_candidate_conflicts': candidate_conflicts,
            'configured_bonus_lines': (configured_selected or {}).get('bonus_lines'),
            'configured_progression': configured_progression,
            'configured_status': ('exact_native_catalog_configuration'
                                  if configured_selected else None),
            'configured_missing': (
                ['Native build 26267212 supplies four configured catalog lines. Owned roll, current-game version, core rank and server activation are separate inputs.']
                + (['A held exact card conflicts with one or more native configured positions; those unobserved values are withheld.']
                   if any(row['source_conflict'] for row in configured_selected['bonus_lines']) else [])
                + (['Shiny shares this native bonus frame; separate Shiny core effect and ownership remain unverified.']
                   if shiny else [])) if configured_selected else None,
            'published_formula_status': selected_published['status'],
            'published_formula_alias_status': selected_published.get('alias_status'),
            'published_formula_alias_sources': selected_published.get('alias_source_urls') or [],
            'shiny_suffix_scope': selected_published.get('shiny_suffix_scope'),
            'shiny_availability_for_identity': selected_published.get('shiny_availability_for_identity'),
            'shiny_core_effect_status': selected_published.get('shiny_core_effect_status'),
            'published_formula_block_reason': selected_published['reason'],
            'source_version': {'catalog_snapshot': catalog.DATA['catalog_version'],
                               'official_level_chart': catalog.DATA['official_rules']['mod_levels']['source'],
                               'current_community_snapshot': catalog.CURRENT['retrieved_utc'],
                               'published_formula_retrieved': published_bonus_lines.FACTS['retrieved_utc_date']},
            'coverage': {'known_numeric_lines': selected['known_numeric_lines'],
                         'total_lines': 4,
                         'observed_numeric_lines': sum(row['status'] in ('value_available', 'observed_value_published_conflict')
                                                       or (row.get('native_corroboration') or {}).get('status') in
                                                       ('recorded_card_value_agrees', 'numeric_agrees_label_differs')
                                                       for row in selected['bonus_lines']),
                         'native_configured_numeric_lines': sum(row['status'] == 'exact_native_catalog_configuration'
                                                                for row in selected['bonus_lines']),
                         'published_candidate_numeric_lines': sum(row['status'].startswith('published_formula_candidate')
                                                                 for row in selected['bonus_lines'])},
            'missing': ([note for note in resolved['unknowns'] if not (
                         selected['known_numeric_lines'] and note.startswith((
                             'At least one numeric attribute tier', 'Exact sub-attribute values',
                             'The four fixed sub-attribute identities')) or
                         (selected_published['status'] == 'exact_native_catalog_configuration' and
                          note.startswith('Official suffix conditions are known, but magnitudes')))]
                        + (['Native catalog magnitudes are configured; owned selection and server activation remain unverified.']
                           if selected_published['status'] == 'exact_native_catalog_configuration' else [])
                        + (['Published slot/suffix formulas are community candidates; this exact identity and game build are not directly checked.']
                           if selected_published['status'] not in ('blocked', 'exact_native_catalog_configuration') else [])
                        + (['Resonance/Resonant Deviant Energy naming bridge has a Deadshot source anchor; transfer to this identity remains a published-layout candidate.']
                           if selected_published.get('alias_status') else [])
                        + (['Native Shiny item identity and shared four-line frame are verified; ownership and separate Shiny core buff are not inferred.']
                           if shiny and catalog_id in native_mod_identity.TWO_FRAME_IDENTITIES else
                           ['Shiny suffix values are conditional on this identity having a Shiny Lv17 version; availability, ownership and core-effect increase are not inferred.']
                           if shiny else [])
                        + (['The published layout conflicts with this identity\'s held line meaning; exact observed values remain, unobserved conflicting candidates are withheld.']
                           if any(row['published_layout_conflict'] for row in selected['bonus_lines']) else []))}

