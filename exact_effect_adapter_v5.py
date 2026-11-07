"""Evidence-gated exact-main-effect adapter. Use this instead of v4's raw rule adapter.

Preview cards and held video with unknown game build require explicit opt-in.
Every output carries the source mode and remains scoped to one observed level.
"""
from __future__ import annotations

from exact_effect_adapter_v4 import execute as _execute_rule, need, stat
from partial_rule_adapter_v4 import execute_partial as _execute_partial_v4


class EvidenceModeRequired(ValueError):
    pass


def _bullet_siphon(rule:dict,context:dict)->dict:
    consumed=need(context,'bullets_consumed_in_magazine')
    if not isinstance(consumed,int) or consumed<0:raise ValueError('invalid bullets consumed')
    base,counter=rule['nodes']
    steps=consumed//counter['per_bullets_consumed']
    extra=min(steps*counter['value_per_step'],counter['max_bonus_percent'])
    return {'outputs':[stat(base['stat'],base['value'],component='base'),
                       stat(counter['stat'],extra,component='magazine_counter',
                            bullets_consumed=consumed,reset='new_magazine')],
            'unresolved':[],'whole_dps_certified':False}


def execute_binding(binding:dict,context:dict,*,allow_preview:bool=False,
                    allow_unknown_game_build:bool=False)->dict:
    """Run one exact binding with evidence-mode gates; never certify current DPS."""
    evidence=binding['evidence_class']
    if evidence=='official_preview_card' and not allow_preview:
        raise EvidenceModeRequired('official preview card requires allow_preview=True')
    if evidence=='held_game_video' and binding.get('game_version')=='unknown' and not allow_unknown_game_build:
        raise EvidenceModeRequired('held video with unknown game build requires allow_unknown_game_build=True')
    if evidence not in {'official_preview_card','held_game_video','current_field_guide_frame'}:
        raise EvidenceModeRequired('unsupported evidence class: '+str(evidence))
    rule=binding['rule'];op=rule['operator']
    if op=='base_plus_magazine_counter':answer=_bullet_siphon(rule,context)
    elif op=='previous_magazine_event_counter':answer=_execute_partial_v4(rule,context)
    else:answer=_execute_rule(rule,context)
    if evidence=='official_preview_card':
        warning='Official preview only; output cannot be treated as a current released level value.'
    elif evidence=='held_game_video':
        warning='Held game video build version unknown; output is not current-version certified.'
    else:
        warning=('Observed mod card wording at this identity and displayed level; '
                 'the active equipped core rank and later game versions are not established.')
    return {**answer,'evidence_class':evidence,'evidence_mode_opt_in':
            'preview' if evidence=='official_preview_card' else
            'unknown_game_build' if evidence=='held_game_video' else 'observed_field_guide',
            'source_warning':warning,'source_url':binding.get('source_url'),
            'source_sha256':binding.get('source_sha256'),
            'catalog_id':binding['catalog_id'],'observed_level':binding['level'],
            'variant_kind':binding['variant_kind'],
            'active_owned_core_proven':False,
            'displayed_level_to_active_entry_rank_proven':False,
            'numeric_binding_scope':'this_identity_level_variant_and_source_only',
            'current_version_certified':False,'whole_dps_certified':False}
