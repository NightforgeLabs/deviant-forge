"""Explicit mathematical reference for legacy mechanics tests only.

The imported weapon_list value is an arbitrary fixture input here. These tests
exercise pool/event/rotation arithmetic, not the live product's source basis.
Default product behavior is tested separately in test_weapon_progression_quarantine.
"""
from unittest import mock
import json
from pathlib import Path

_FIXTURES = json.loads((Path(__file__).parent / 'fixtures/synthetic_math_inputs.json').read_text())['weapons']
_ARMOR_FIXTURE = json.loads((Path(__file__).parent /
    'fixtures/synthetic_armor_math_table.json').read_text())


def _synthetic_baseline(_packet_dir, weapon_id):
    import published_reference_identity
    canonical, alias = published_reference_identity.weapon_binding(weapon_id)
    row = _FIXTURES.get(canonical)
    if row is None:
        raise LookupError(f'No isolated math fixture for {weapon_id}')
    return {'weapon_id': weapon_id, 'upstream_id': row['upstream_id'],
            'canonical_catalog_id': canonical, 'identity_evidence': alias,
            'name': row['name'], 'rarity': 'fixture', 'stats': dict(row['stats']),
            'source_url': 'isolated-test-fixture', 'snapshot_date': None,
            'evidence': 'published_calculator_source_baseline_unverified_game_basis'}


def _synthetic_progression(baseline, *, stars, tier, calibration):
    if baseline.get('evidence') != 'published_calculator_source_baseline_unverified_game_basis':
        raise ValueError('Synthetic test fixture expects an explicitly named imported input')
    multiplier=(1+0.1*(stars-1))*(1+0.05*(tier-1))*(1+0.02*calibration)
    stats=dict(baseline['stats'])
    original=stats.get('damage_per_projectile')
    stats['damage_per_projectile']=original*multiplier if original is not None else None
    return {'weapon_id':baseline['weapon_id'],'upstream_id':baseline['upstream_id'],
            'stars':stars,'tier':tier,'calibration':calibration,
            'damage_multiplier':multiplier,'stats':stats,'unresolved':[],
            'model':'explicit_synthetic_arithmetic_test_fixture_not_game_damage',
            'game_verified':False,'source_url':baseline['source_url']}


def explicit_synthetic_reference(cls):
    """Scope arithmetic and unique-effect exclusion to one synthetic test instance."""
    original_setup=cls.__dict__.get('setUp')
    def setUp(self):
        import published_timed_combat
        original_evaluate=published_timed_combat.evaluate
        patcher=mock.patch('published_calculator_adapter.derive_published_weapon_progression',
                           side_effect=_synthetic_progression)
        patcher.start();self.addCleanup(patcher.stop)
        baseline_patch=mock.patch('published_calculator_adapter.load_published_weapon_baseline',
                                  side_effect=_synthetic_baseline)
        baseline_patch.start();self.addCleanup(baseline_patch.stop)
        armor_patch=mock.patch('published_calculator_adapter.load_published_armor_table',
                               return_value=_ARMOR_FIXTURE)
        armor_patch.start();self.addCleanup(armor_patch.stop)
        # These legacy fixtures exercise isolated pool/rule arithmetic. Their
        # chosen KAM unique effect is explicitly outside that fixture scope.
        def scoped_evaluate(build, options, **kwargs):
            return original_evaluate(build, {**options,
                'exclude_unbound_weapon_effect': True}, **kwargs)
        evaluate_patch=mock.patch('published_timed_combat.evaluate',
                                  side_effect=scoped_evaluate)
        evaluate_patch.start();self.addCleanup(evaluate_patch.stop)
        if original_setup is not None:
            original_setup(self)
    cls.setUp=setUp
    return cls
