"""Evidence-gated exact timed outputs feed only eligible packet windows."""
import copy
import unittest

import component_compare
import integrated_event_model as model
from tests.test_integrated_event_model import POOLS, request


SHINY = 'mod:pants_mod:elemental-resonance-aero'
CHOICE = {'catalog_id': SHINY, 'level': 17, 'shiny': True, 'allow_preview': True}
TIMING = {'activation': 'event_completion', 'expiry': 'half_open',
          'overlap': 'reject_unresolved'}


def scenario():
    events = [{'kind': 'shot', 'event_id': 'before', 'at': 0},
              {'kind': 'reload', 'event_id': 'reload', 'at': .1,
               'loaded_rounds': 2, 'base_reload_seconds': 1,
               'core_context': {'previous_magazine_elemental_damage_instances': 10}},
              {'kind': 'shot', 'event_id': 'active', 'at': 1.1},
              {'kind': 'shot', 'event_id': 'expired', 'at': 16.1}]
    entered = request(events, duration=17, capacity=3, magazine=1, reserve=2)
    entered['direct_packet']['element'] = 'shock'
    entered['exact_timed_mods'] = [CHOICE.copy()]
    entered['exact_timed_assumptions'] = TIMING.copy()
    return entered


class ExactTimedCoreIntegration(unittest.TestCase):
    def test_reload_completion_and_half_open_expiry(self):
        entered = scenario()
        before = copy.deepcopy(entered)
        out = model.evaluate(entered, static_pools=POOLS)
        self.assertEqual([round(x['damage']) for x in out['packets']], [100, 110, 100])
        self.assertEqual(out['total_damage'], 310)
        self.assertEqual(out['exact_timed_sources'][0]['windows'][0]['start'], 1.1)
        self.assertEqual(out['exact_timed_sources'][0]['windows'][0]['end'], 16.1)
        self.assertFalse(out['current_level_certified'])
        self.assertIn('official_preview_card', str(out['unresolved']))
        self.assertEqual(entered, before)

    def test_preview_variant_context_and_assumptions_gate(self):
        entered = scenario()
        entered['exact_timed_mods'][0]['allow_preview'] = False
        with self.assertRaisesRegex(ValueError, 'preview opt-in'):
            model.evaluate(entered, static_pools=POOLS)
        entered = scenario()
        entered['exact_timed_mods'][0]['shiny'] = False
        with self.assertRaisesRegex(ValueError, 'variant mismatch'):
            model.evaluate(entered, static_pools=POOLS)
        entered = scenario()
        del entered['events'][1]['core_context']
        with self.assertRaisesRegex(ValueError, 'previous_magazine_elemental_damage_instances'):
            model.evaluate(entered, static_pools=POOLS)
        entered = scenario()
        del entered['exact_timed_assumptions']
        with self.assertRaisesRegex(ValueError, 'named event completion'):
            model.evaluate(entered, static_pools=POOLS)

    def test_element_only_and_overlapping_trigger_rejected(self):
        entered = scenario()
        entered['direct_packet']['element'] = 'none'
        out = model.evaluate(entered, static_pools=POOLS)
        self.assertEqual(out['total_damage'], 300)
        entered = scenario()
        entered['events'].insert(2, {'kind': 'reload', 'event_id': 'reload2', 'at': 1.1,
                                      'loaded_rounds': 0, 'base_reload_seconds': 0,
                                      'core_context': {'previous_magazine_elemental_damage_instances': 1}})
        with self.assertRaisesRegex(ValueError, 'retrigger overlaps'):
            model.evaluate(entered, static_pools=POOLS)

    def test_compare_requires_selected_exact_variant(self):
        selected = {'catalog_id': SHINY, 'level': 17, 'shiny': True}
        left = scenario()
        right = scenario()
        context = {'base_pools': {**POOLS, 'crit': 0, 'weakspot': 0},
                   'condition_uptime': {'aerial hit': 0},
                   'condition_strength': {'aerial hit': 0},
                   'integrated_combat': {'left': left, 'right': right}}
        out = component_compare.compare(selected, selected, context)
        self.assertAlmostEqual(out['integrated_event_scenarios']['left']['total_damage'],
                               310 * 1.06 * 1.075)
        self.assertFalse(out['game_winner_established'])
        context['integrated_combat']['right']['exact_timed_mods'][0]['shiny'] = False
        with self.assertRaisesRegex(ValueError, 'must match selected gear or plan'):
            component_compare.compare(selected, selected, context)


if __name__ == '__main__':
    unittest.main()
