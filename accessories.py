"""Small, screenshot-backed accessory catalog. No ownership is inferred here."""

ITEMS = {
    'accessory:tactical-suppressor': {
        'id': 'accessory:tactical-suppressor', 'name': 'Tactical Suppressor',
        'slot': 'muzzle', 'rarity': 'gold',
        'effects': [('Bullet Velocity', 10), ('Stability', -12), ('Range', 20)],
        'compatibility': 'Pistols, SMGs, Assault Rifles, LMGs',
        'weapon_classes': ('pistol', 'smg', 'assault rifle', 'lmg'),
        'source_ref': 'libfile_52fbfd7e7ed88191bb114bdd8f9a4b77',
        'artwork': '/artwork/accessory-tactical-suppressor.png',
    },
    'accessory:tactical-flash-hider': {
        'id': 'accessory:tactical-flash-hider', 'name': 'Tactical Flash Hider',
        'slot': 'muzzle', 'rarity': 'purple',
        'effects': [('Stability', 16)],
        'compatibility': 'Pistols, SMGs, Assault Rifles, LMGs',
        'weapon_classes': ('pistol', 'smg', 'assault rifle', 'lmg'),
        'source_ref': 'libfile_797f87de69f48191a979a43b1d12d006',
        'artwork': '/artwork/accessory-tactical-flash-hider.png',
    },
    'accessory:compact-reflex-sight': {
        'id': 'accessory:compact-reflex-sight', 'name': 'Compact Reflex Sight',
        'slot': 'optic', 'rarity': 'gold', 'zoom': 2,
        'effects': [('Mobility', 20), ('Aiming Speed', 20), ('Accuracy', 6)],
        'compatibility': 'R500, DE.50, DB12, S870, SMGs, Assault Rifles, LMGs, Sniper Rifles',
        'weapon_prefixes': ('R500', 'DE.50', 'DB12', 'S870'),
        'weapon_classes': ('smg', 'assault rifle', 'lmg', 'sniper rifle'),
        'source_ref': 'libfile_2f72a11159e88191ae089f4e3e08c7db',
        'artwork': '/artwork/accessory-compact-reflex-sight.png',
    },
    'accessory:alpha-holographic-sight': {
        'id': 'accessory:alpha-holographic-sight', 'name': 'ALPHA Holographic Sight',
        'slot': 'optic', 'rarity': 'gold', 'zoom': 2,
        'effects': [('Mobility', 20), ('Aiming Speed', 20), ('Accuracy', 6)],
        'compatibility': 'DB12, S870, SMGs, Assault Rifles, LMGs, Sniper Rifles',
        'weapon_prefixes': ('DB12', 'S870'),
        'weapon_classes': ('smg', 'assault rifle', 'lmg', 'sniper rifle'),
        'source_ref': 'libfile_426e618e55ac81918b5b3c41825b6282',
        'artwork': '/artwork/accessory-alpha-holographic-sight.png',
    },
    'accessory:fastened-mini-reflex-sight': {
        'id': 'accessory:fastened-mini-reflex-sight', 'name': 'Fastened Mini Reflex Sight',
        'slot': 'optic', 'rarity': 'purple', 'zoom': 2,
        'effects': [('Aiming Speed', 15), ('Accuracy', 6)],
        'compatibility': 'DB12, S870, SMGs, Assault Rifles, LMGs, Sniper Rifles',
        'weapon_prefixes': ('DB12', 'S870'),
        'weapon_classes': ('smg', 'assault rifle', 'lmg', 'sniper rifle'),
        'source_ref': 'libfile_26a780084c9481919a1f8b6ab9a8c4cd',
        'artwork': '/artwork/accessory-fastened-mini-reflex-sight.png',
    },
    'accessory:recon-combat-optic': {
        'id': 'accessory:recon-combat-optic', 'name': 'Recon Combat Optic',
        'slot': 'optic', 'rarity': 'purple', 'zoom': 4,
        'effects': [('Accuracy', 8)],
        'compatibility': 'Assault Rifles, LMGs, Sniper Rifles',
        'weapon_classes': ('assault rifle', 'lmg', 'sniper rifle'),
        'source_ref': 'libfile_2fc771017ce88191886013c4d22ab4c2',
        'artwork': '/artwork/accessory-recon-combat-optic.png',
    },
    'accessory:light-front-grip': {
        'id': 'accessory:light-front-grip', 'name': 'Light Front Grip',
        'slot': 'tactics', 'rarity': 'gold',
        'effects': [('Mobility', 15), ('Aiming Speed', 20), ('Hit Shake Resistance', 20), ('Stability', 15)],
        'compatibility': 'KV-SBR, MPS5, SOCR, M416 series',
        'weapon_prefixes': ('KV-SBR', 'MPS5', 'SOCR', 'M416'),
        'source_ref': 'libfile_63e13d513a1c81918e6e0b89baa729d0',
        'artwork': '/artwork/accessory-light-front-grip.png',
    },
    'accessory:elite-vertical-grip': {
        'id': 'accessory:elite-vertical-grip', 'name': 'Elite Vertical Grip',
        'slot': 'tactics', 'rarity': 'gold',
        'effects': [('Mobility', -12), ('Stability', 24)],
        'compatibility': 'KV-SBR, MPS5, SOCR, KAM above Common rarity, M416 series',
        'weapon_prefixes': ('KV-SBR', 'MPS5', 'SOCR', 'M416'),
        'rarity_gated_prefixes': (('KAM', ('rare', 'epic', 'legendary')),),
        'source_ref': 'libfile_e0d88282fbfc8191a43f51cc7fc31611',
        'artwork': '/artwork/accessory-elite-vertical-grip.png',
    },
    'accessory:infrared-indicator': {
        'id': 'accessory:infrared-indicator', 'name': 'Infrared Indicator',
        'slot': 'tactics', 'rarity': 'purple',
        'effects': [('Stability', 13), ('Accuracy', 10)],
        'compatibility': 'Shotguns, SMGs, Assault Rifles, Sniper Rifles, LMGs',
        'weapon_classes': ('shotgun', 'smg', 'assault rifle', 'sniper rifle', 'lmg'),
        'source_ref': 'libfile_bfb18e4ab9f08191a8fca3cbe6994716',
        'artwork': '/artwork/accessory-infrared-indicator.png',
    },
    'accessory:amended-rifle-mag': {
        'id': 'accessory:amended-rifle-mag', 'name': 'Amended Rifle Mag',
        'slot': 'magazine', 'rarity': 'blue',
        'effects': [('Reload Speed', 10), ('Accuracy', 8)],
        'compatibility': 'Assault Rifles',
        'weapon_classes': ('assault rifle',),
        'source_ref': 'libfile_e2363f62840c819199a0cc5378da9977',
        'artwork': '/artwork/accessory-amended-rifle-mag.png',
    },
}

ACQUISITION = 'Acc Interface using Precision Components from Blueprints Collection level rewards'


def weapon_class(entry, art_record=None):
    """Return a weapon class only when its catalog spelling or sourced art supplies one."""
    category = str((art_record or {}).get('weapon_category') or '').lower()
    family = str(entry.get('family') or '').lower()
    if category in ('assault rifle', 'smg', 'lmg', 'pistol', 'sniper rifle', 'shotgun'):
        return category
    if family == 'assault_rifl':
        return 'assault rifle'
    if family == 'smgs':
        return 'smg'
    if family in ('pistols', 'lmgs'):
        return family[:-1]
    if family=='sniper_rifles':
        return 'sniper rifle'
    if family=='shotgun':
        return 'shotgun'
    return None


def compatible(item, weapon, art_record=None):
    if not weapon or weapon.get('kind') != 'weapon':
        return False
    name = str(weapon.get('name') or '')
    named = any(name == prefix or name.startswith(prefix + ' - ') for prefix in item.get('weapon_prefixes', ()))
    rarity_gated = any(
        (name == prefix or name.startswith(prefix + ' - ')) and weapon.get('rarity') in allowed
        for prefix, allowed in item.get('rarity_gated_prefixes', ())
    )
    return named or rarity_gated or weapon_class(weapon, art_record) in item.get('weapon_classes', ())


def public_items():
    return [{k: v for k, v in item.items() if k not in ('weapon_classes', 'weapon_prefixes', 'rarity_gated_prefixes')}
            | {'acquisition': ACQUISITION} for item in ITEMS.values()]
