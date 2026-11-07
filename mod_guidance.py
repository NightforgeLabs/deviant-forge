"""Read-only, evidence-labeled mod matches. No damage ranking is implied."""

GOALS = {
    'burn': {'label': 'Burn Mod', 'specific': ('burn', 'blaze'), 'broad': ('element dmg', 'elemental dmg', 'elemental damage')},
    'electric': {'label': 'Power Surge Mod', 'specific': ('power surge', 'shock dmg', 'shock damage'), 'broad': ('element dmg', 'elemental dmg', 'elemental damage')},
    'frost': {'label': 'Frost Vortex Mod', 'specific': ('frost vortex', 'frost dmg', 'frost damage'), 'broad': ('element dmg', 'elemental dmg', 'elemental damage')},
    'bullseye': {'label': 'The Bullseye Mod', 'specific': ('bulls eye', "bull's eye", 'bullseye'), 'broad': ()},
    'fortress_warfare': {'label': 'Fortress Warfare Mod', 'specific': ('fortress warfare',), 'broad': ()},
    'unstable_bomber': {'label': 'Unstable Bomber Mod', 'specific': ('unstable bomber',), 'broad': ()},
    'fast_gunner': {'label': 'Fast Gunner Mod', 'specific': ('fast gunner',), 'broad': ()},
    'bounce': {'label': 'Bounce Mod', 'specific': ('bounce',), 'broad': ()},
    'shrapnel': {'label': 'Shrapnel Mod', 'specific': ('shrapnel',), 'broad': ()},
}

ARMOR_MOD_SLOTS = {'helmet_mod': 'helmet', 'mask_mod': 'mask', 'chest_mod': 'top',
                   'pants_mod': 'bottoms', 'gloves_mod': 'gloves', 'boots_mod': 'shoes'}


def suggest(catalog, inventory, goal, weapon_id=None, slots=None, weapon_slot='primary'):
    if goal not in GOALS:
        raise ValueError('Choose a supported damage goal')
    weapon = catalog.ENTRIES.get(weapon_id) if weapon_id else None
    if weapon_id and (not weapon or weapon.get('kind') != 'weapon'):
        raise ValueError('Choose a cataloged weapon')
    slots = slots or {}
    if not isinstance(slots, dict):
        raise ValueError('Invalid build slots')
    if weapon_slot not in ('primary', 'secondary'):
        weapon_slot = 'primary'
    owned = {}
    for item in inventory:
        identity = item.get('effects', {}).get('catalog_id')
        if item.get('kind') == 'mod_unlock' and identity in catalog.ENTRIES:
            owned.setdefault(identity, []).append({'id': item['id'], 'level': item.get('level')})
    terms = GOALS[goal]
    candidates = []
    for entry in catalog.ENTRIES.values():
        if entry.get('kind') != 'mod':
            continue
        slot = entry.get('slot')
        if slot != 'weapon_mod' and slot not in ARMOR_MOD_SLOTS:
            continue
        effect = entry.get('primary_effect') or entry.get('effect') or ''
        name = entry.get('display_name') or entry.get('name') or ''
        searchable = (name + ' ' + effect).lower()
        matched = [term for term in terms['specific'] if term in searchable]
        broad = False
        if not matched:
            matched = [term for term in terms['broad'] if term in searchable]
            broad = bool(matched)
        if not matched:
            continue
        target = weapon_slot if slot == 'weapon_mod' else ARMOR_MOD_SLOTS[slot]
        available = bool(slots.get(target, {}).get('catalog_id'))
        instances = owned.get(entry['id'], [])
        profiles = catalog.NUMERIC['profiles'].get(entry['id']) or {}
        candidates.append({
            'id': entry['id'], 'name': name, 'slot': slot, 'target_slot': target,
            'base_name': entry.get('name') or name, 'variant': entry.get('variant'),
            'group': 'weapon' if slot == 'weapon_mod' else 'armor',
            'effect': effect, 'source_url': entry.get('source_url'),
            'source': entry.get('source'), 'match': 'broad elemental' if broad else 'named mechanic',
            'matched_terms': matched, 'owned_instances': instances,
            'verified_numeric_levels': sorted(int(level) for level in profiles),
            'can_equip_in_current_build': available,
            'evidence_limit': 'Catalog effect wording is a candidate match; its actual trigger, uptime and damage impact are unverified.',
        })
    # Evidence grouping only; no damage score or winner is inferred.
    candidates.sort(key=lambda x: (x['group'] != 'weapon', x['match'] != 'named mechanic',
                                   x['slot'], x['base_name'].lower(),
                                   not bool(x['verified_numeric_levels']), not bool(x['source_url']), x['name'].lower()))
    overall = {'weapon': [], 'armor': []}
    personal = {'weapon': [], 'armor': []}
    for candidate in candidates:
        overall[candidate['group']].append(candidate)
        if candidate['owned_instances']:
            personal[candidate['group']].append(candidate)
    weapon_text = ((weapon.get('display_name') or weapon.get('name') or '') + ' ' +
                   (weapon.get('primary_effect') or weapon.get('effect') or '') + ' ' +
                   (weapon.get('family') or '')).lower() if weapon else ''
    family_terms = ('power surge', 'shock') if goal == 'electric' else terms['specific']
    compatible_family = any(term in weapon_text for term in family_terms)
    return {
        'goal': goal, 'goal_label': terms['label'], 'weapon_id': weapon_id,
        'weapon_family_match': compatible_family,
        'weapon_note': 'Weapon catalog wording names this mechanic; actual trigger and damage are unverified.' if compatible_family else
                       'No matching weapon mechanic is documented. Check the game tooltip before using this shortlist.',
        'method': 'Catalog wording matched to named mechanic, then broader elemental wording. Distinct variants remain separate; numeric observations affect evidence order only. No DPS ranking.',
        'overall': overall, 'owned': personal,
    }
