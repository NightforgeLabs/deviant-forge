"""Read-only selected-mod observations. Source text never activates a modifier."""
import field_guide_profiles


def selected_rows(slots, connection, inventory_items):
    result = []
    for slot, choice in slots.items():
        if not isinstance(choice, dict) or not choice.get('mod_id'):
            continue
        identity, level = choice['mod_id'], choice.get('mod_level')
        item = {'slot': slot, 'catalog_id': identity, 'selected_level': level,
                'status': 'missing_exact_rows', 'rows': [], 'activation': 'unknown',
                'calculation_included': False}
        if not isinstance(level, int) or isinstance(level, bool) or not 1 <= level <= 17:
            item['reason'] = 'Select the exact mod level before looking up its bonus lines.'
            result.append(item)
            continue
        # Reviewed rank cells are shared catalog evidence, not profile ownership.
        reviewed = field_guide_profiles.preview(connection, 'new_player', identity, level, 'unknown')
        observed = reviewed.get('reviewed_exact_rows') or []
        if observed and any(row.get('confidence') == 'source_checked' for row in observed):
            item['status'] = 'reviewed_same_rank' if reviewed.get('rank_derived') else 'reviewed_exact_level'
            item['rows'] = [{'position': row.get('row_index', index) + 1,
                             'text': row.get('raw_text') or f'Row {index + 1}: value unobserved',
                             'stat_type': row.get('stat_type'), 'value': row.get('value'),
                             'source_level': (row.get('evidence') or {}).get('observed_level'),
                             'source_ref': (row.get('evidence') or {}).get('source_tooltip') or
                                           (row.get('evidence') or {}).get('source_frame'),
                             'confidence': row.get('confidence')}
                            for index, row in enumerate(observed)]
            item['reason'] = ('Same-position, same-rank observations from another level; this level was not photographed.'
                              if reviewed.get('rank_derived') else 'Reviewed exact-level tooltip rows.')
            result.append(item)
            continue
        matches = [record for record in inventory_items
                   if record.get('level') == level and
                   (record.get('effects') or {}).get('catalog_id') == identity and
                   (record.get('stats') or {}).get('observed_tooltip', {}).get('attribute_lines')]
        if len(matches) > 1:
            item['status'] = 'ambiguous_records'
            item['reason'] = 'Multiple matching records have tooltip lines; choose the exact source before using either.'
        elif matches:
            stats = matches[0].get('stats') or {}
            tooltip = stats['observed_tooltip']
            observed_level = (tooltip.get('observed_level') or stats.get('original_observed_level') or
                              (stats.get('screenshot_import') or {}).get('observed_level'))
            if observed_level is not None and observed_level != level:
                item['status'] = 'source_level_mismatch'
                item['reason'] = f'Tooltip evidence is Lv {observed_level}, not selected Lv {level}.'
            elif tooltip.get('source_ref'):
                item['status'] = 'existing_record_tooltip'
                item['rows'] = [{'position': index + 1, 'text': str(text), 'stat_type': None,
                                 'value': None, 'source_level': level,
                                 'source_ref': tooltip['source_ref'], 'confidence': 'source_text_only'}
                                for index, text in enumerate(tooltip['attribute_lines'])]
                item['reason'] = 'Exact-level existing-record tooltip text; item system and Tech activation remain unverified.'
        if not item.get('reason'):
            item['reason'] = 'No reviewed bonus values for this exact variant and level. A level badge does not supply magnitudes.'
        result.append(item)
    return result
