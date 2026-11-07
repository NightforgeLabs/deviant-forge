"""Read-only, instance-aware planning for reviewed video mod evidence.

Catalog identity is a type of mod, not an owned instance identifier. A matching
type and level is a review target, never permission to overwrite that instance.
"""
import hashlib
import json
from collections import Counter, defaultdict
import mod_rolls
import field_guide_profiles


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def _source_checked(data):
    audit = data.get("source_audit") or {}
    return (str(audit.get("status") or "").startswith("source_text_and_numbers_checked")
            and (audit.get("main_effect") or {}).get("source_text") == data.get("main_effect")
            and [row.get("source_text") for row in audit.get("attribute_rows") or []]
            == (data.get("attribute_rows") or []))


def plan(run_id, proposals, inventory):
    """Return an immutable-to-caller review plan; never mark ownership or Tech active."""
    owned = defaultdict(list)
    for item in inventory:
        if item.get("kind") != "mod_unlock" or item.get("archived"):
            continue
        catalog_id = (item.get("effects") or {}).get("catalog_id")
        if catalog_id:
            owned[catalog_id].append(item)
    rows = [row for row in proposals if row.get("run_id") == run_id]
    competing = defaultdict(list)
    field_observations = defaultdict(list)
    for row in rows:
        data = row.get("data") or {}
        if row.get("status") != "dismissed" and data.get("ownership") == "unlocked":
            competing[(data.get("catalog_id"), data.get("level"),data.get('shiny_status','unknown'))].append(row)
            if field_guide_profiles.source_system(data)==field_guide_profiles.SYSTEM:
                field_observations[data.get('catalog_id')].append(row)
    entries = []
    counts = Counter()
    for row in rows:
        data = row.get("data") or {}
        if row.get("status") == "dismissed":
            continue
        if data.get("ownership") != "unlocked":
            counts["source_locked_or_unknown"] += 1
            continue
        catalog_id, level = data.get("catalog_id"), data.get("level")
        source = data.get("source") or {}
        typed = data.get("typed_modifiers") or []
        raw = data.get("attribute_rows") or []
        matches = [item for item in owned[catalog_id] if item.get("level") == level]
        other_levels = [item for item in owned[catalog_id] if item.get("level") != level]
        peers = competing[(catalog_id, level,data.get('shiny_status','unknown'))]
        source_system=field_guide_profiles.source_system(data)
        if row.get("status") == "committed":
            classification = "already_committed"
        elif source_system==field_guide_profiles.SYSTEM:
            field_peers=field_observations[catalog_id]
            shiny_states={candidate['data'].get('shiny_status','unknown') for candidate in field_peers}
            if len(shiny_states)>1:
                classification='field_guide_shiny_identity_needs_review'
            elif len(peers)>1:
                readings={(tuple(candidate['data'].get('attribute_rows') or []),candidate['data'].get('main_effect')) for candidate in peers}
                frames={(str((candidate['data'].get('source') or {}).get('frame')),
                         (candidate['data'].get('source') or {}).get('timestamp')) for candidate in peers}
                classification=('field_guide_conflicting_observations' if len(readings)>1 else
                                'field_guide_duplicate_source' if len(frames)==1 else
                                'field_guide_repeated_hover')
            elif any(candidate['data'].get('level')!=level for candidate in field_peers):
                verified_levels=[candidate['data'].get('level') for candidate in field_peers
                                 if isinstance(candidate['data'].get('level'),int)]
                classification=('field_guide_stale_lower_observation' if verified_levels and level<max(verified_levels)
                                else 'field_guide_higher_level_candidate')
            else:
                classification = "field_guide_progression_needs_profile_review"
        elif source_system!=field_guide_profiles.LEGACY_SYSTEM:
            classification = "source_system_needs_review"
        elif len(peers) > 1:
            # Identical source-frame addresses prove a repeated observation;
            # matching text on different frames does not prove one owned copy.
            source_keys={(str((candidate['data'].get('source') or {}).get('frame')),
                          (candidate['data'].get('source') or {}).get('timestamp')) for candidate in peers}
            roll_keys={(tuple(candidate['data'].get('attribute_rows') or []),
                        candidate['data'].get('main_effect')) for candidate in peers}
            if len(source_keys)==1:
                classification = "duplicate_source_observation"
            elif len(roll_keys)>1:
                classification = "conflicting_source_or_distinct_copy_needs_review"
            else:
                classification = "repeated_hover_or_distinct_copy_needs_review"
        elif len(matches) > 1:
            classification = "multiple_existing_copies_need_identity_review"
        elif matches:
            classification = "existing_identity_level_needs_evidence_review"
        elif other_levels:
            classification = "existing_variant_other_level_needs_identity_review"
        elif not _source_checked(data):
            classification = "needs_source_review"
        else:
            classification = "new_owned_copy_candidate"
        counts[classification] += 1
        counts["raw_attribute_rows"] += len(raw)
        counts["typed_attribute_rows"] += len(typed)
        counts["ambiguous_signed_rows"] += sum(
            item.get("calculation_status") == "excluded_ambiguous" for item in typed)
        entries.append({
            "proposal_id": row.get("id"), "catalog_id": catalog_id,
            "slot": data.get("slot"), "variant": data.get("variant"), "level": level,
            "source_system": source_system or "unknown",
            "classification": classification, "source_checked": _source_checked(data),
            "source_frame": source.get("frame"), "source_timestamp": source.get("timestamp"),
            "raw_attribute_rows": len(raw), "typed_attribute_rows": len(typed),
            "matching_owned_instance_ids": [item.get("id") for item in matches],
            "other_owned_levels": sorted({item.get("level") for item in other_levels if item.get("level") is not None}),
            "tech_activation": "unknown",
            "requires_explicit_commit": row.get("status") != "committed",
        })
    return {"run_id": run_id, "counts": dict(counts), "entries": entries,
            "plan_token": _digest({"entries": entries, "owned": sorted([
                (item.get("id"), item.get("level"), (item.get("effects") or {}).get("catalog_id"),
                 (item.get("stats") or {}).get("observed_attribute_lines"),
                 (item.get("stats") or {}).get("typed_modifiers"),
                 (item.get("stats") or {}).get("video_import"))
                for group in owned.values() for item in group], key=lambda row: str(row[0]))})}


def legacy_observation_staging(media_id, observations, inventory):
    """Preview old confirmed OCR evidence without changing the owned instances.

    A confirmed observation is not a source check of its individual numbers.  In
    particular, parsed OCR rows remain inactive until the original is reviewed.
    """
    by_observation = defaultdict(list)
    for item in inventory:
        if item.get('kind') == 'mod_unlock' and not item.get('archived'):
            by_observation[item.get('source_observation')].append(item)
    entries = []
    unresolved = Counter()
    for observation in observations:
        if observation.get('media_id') != media_id or observation.get('state') != 'confirmed':
            continue
        fields = observation.get('fields') or {}
        identity = fields.get('identification') or {}
        catalog_id = identity.get('catalog_id')
        if not catalog_id or not catalog_id.startswith('mod:'):
            continue
        raw = (fields.get('mod_roll_lines') or {}).get('value') or []
        if not isinstance(raw, list):
            raw = []
        linked = by_observation.get(observation.get('id'), [])
        raw_origin = 'observation_ocr'
        if not raw and len(linked) == 1:
            # One older confirmation retained its OCR line on the inventory
            # instance but not on the observation. Show that exact linked
            # source, without claiming a fresh source-frame check.
            raw = (linked[0].get('stats') or {}).get('observed_attribute_lines') or []
            raw_origin = 'linked_owned_ocr'
        typed = mod_rolls.parse_rows(raw, source={'frame': observation.get('image'),
                                                   'timestamp': observation.get('timestamp')})
        for row in typed:
            if row['stat_type'] == 'unparsed':
                unresolved[row['raw_text']] += 1
        entries.append({'observation_id': observation.get('id'), 'catalog_id': catalog_id,
                        'slot': identity.get('slot'), 'variant': identity.get('variant'),
                        'level': identity.get('level'), 'source_frame': observation.get('image'),
                        'source_timestamp': observation.get('timestamp'),
                        'raw_attribute_rows': raw, 'raw_origin': raw_origin, 'typed_modifiers': typed,
                        'matching_owned_instance_ids': [item['id'] for item in linked],
                        'source_checked': False, 'tech_activation': 'unknown',
                        'requires_row_review': True})
    return {'media_id': media_id, 'entries': entries,
            'counts': {'confirmed_mod_observations': len(entries),
                       'raw_attribute_rows': sum(len(e['raw_attribute_rows']) for e in entries),
                       'linked_owned_instances': sum(len(e['matching_owned_instance_ids']) for e in entries),
                       'typed_attribute_rows': sum(len(e['typed_modifiers']) for e in entries),
                       'unparsed_attribute_rows': sum(unresolved.values())},
            'unresolved_parser_labels': [{'raw_text': label, 'count': count}
                                         for label, count in unresolved.most_common()]}
