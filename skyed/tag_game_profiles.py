from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass(frozen=True)
class TagGameProfile:
    key: str
    label: str
    description: str
    default_category: str
    source_focus: str
    imported_from: List[str] = field(default_factory=list)
    default_settings: Dict[str, Any] = field(default_factory=dict)


GAME_ORDER: List[str] = [
    "touch_listen_cards",
    "listen_click_choice",
    "matching_pairs",
    "memory_pairs",
    "image_cards",
    "reveal_guess",
    "animal_mystery",
    "concentration",
    "desert_drag",
    "slow_click",
    "speed_balls",
    "phrase_maker",
    "describer",
    "bubbles_english",
    "spelling_bee",
    "hangman",
    "falling_english",
    "fast_phrases",
    "fast_english",
]


GAME_PROFILES: Dict[str, TagGameProfile] = {
    "touch_listen_cards": TagGameProfile(
        key="touch_listen_cards",
        label="Touch and Listen",
        description="Tap picture cards to play audio. Best for very young learners, review, and NG top embeds.",
        default_category="Vocabulary",
        source_focus="vocab",
        default_settings={"columns": 4, "show_translation": True, "tile_min_px": 210},
    ),
    "listen_click_choice": TagGameProfile(
        key="listen_click_choice",
        label="Listen and Choose",
        description="Play the prompt and choose the correct picture from a grid of options.",
        default_category="Vocabulary",
        source_focus="vocab_audio",
        default_settings={"choice_count": 4, "round_limit": 10, "auto_play": True, "show_translation": True},
    ),
    "matching_pairs": TagGameProfile(
        key="matching_pairs",
        label="Matching Pairs",
        description="Match bilingual or picture-text pairs in a branded practice board.",
        default_category="Vocabulary",
        source_focus="vocab",
        default_settings={"show_audio_button": True, "show_images": True},
    ),
    "memory_pairs": TagGameProfile(
        key="memory_pairs",
        label="Memory Pairs",
        description="Classic memory flip game using image-word pairs.",
        default_category="Vocabulary",
        source_focus="vocab",
        default_settings={"grid_min_px": 150, "show_translation": True},
    ),
    "image_cards": TagGameProfile(
        key="image_cards",
        label="Image Cards",
        description="Calm study deck with Previous / Next navigation and optional audio.",
        default_category="Vocabulary",
        source_focus="vocab",
        default_settings={"show_translation": True, "loop_audio": False},
    ),
    "reveal_guess": TagGameProfile(
        key="reveal_guess",
        label="Reveal and Guess",
        description="Reveal part of the image, then guess the correct answer from several options.",
        default_category="Vocabulary",
        source_focus="vocab_audio",
        default_settings={"choice_count": 4, "reveal_steps": 4, "round_limit": 10},
    ),
    "animal_mystery": TagGameProfile(
        key="animal_mystery",
        label="Animal Mystery",
        description="Guess the mystery card by revealing clues one by one, then selecting the answer.",
        default_category="Sentence Patterns",
        source_focus="vocab_clues",
        imported_from=["AnimalMysterySetup32.0.1.rar"],
        default_settings={"choice_count": 6, "max_clues": 4, "round_limit": 6},
    ),
    "concentration": TagGameProfile(
        key="concentration",
        label="Concentration",
        description="Imported family equivalent of a classic concentration memory game.",
        default_category="Vocabulary",
        source_focus="vocab",
        imported_from=["ConcentrationSetup32.0.1.rar"],
        default_settings={"grid_min_px": 150, "show_translation": True, "cover_badge": "Concentrate"},
    ),
    "desert_drag": TagGameProfile(
        key="desert_drag",
        label="Desert Drag",
        description="Drag word labels onto the correct image cards. Works well with vocabulary themes.",
        default_category="Vocabulary",
        source_focus="vocab",
        imported_from=["DesertDrag.rar"],
        default_settings={"round_limit": 8, "show_translation": False},
    ),
    "slow_click": TagGameProfile(
        key="slow_click",
        label="Slow Click",
        description="Large, slower-paced listen-and-click rounds with strong visual separation for younger learners.",
        default_category="Vocabulary",
        source_focus="vocab_audio",
        imported_from=["SlowClick.rar"],
        default_settings={"choice_count": 4, "round_limit": 8, "auto_play": True, "button_style": "slow"},
    ),
    "speed_balls": TagGameProfile(
        key="speed_balls",
        label="Speed Balls",
        description="Timed rapid-choice mode with score pressure and quick rounds.",
        default_category="Vocabulary",
        source_focus="vocab_audio",
        imported_from=["SpeedBalls.rar"],
        default_settings={"choice_count": 4, "timer_seconds": 45, "round_limit": 15},
    ),
    "phrase_maker": TagGameProfile(
        key="phrase_maker",
        label="Phrase Maker",
        description="Rebuild phrases or sentences from shuffled tokens. Uses #Sentences, #Questions and answers, or reading lines.",
        default_category="Sentence Patterns",
        source_focus="sentences",
        imported_from=["PhraseMakerSetup32.0.1.rar"],
        default_settings={"round_limit": 10, "token_source": "sentences", "show_translation": True},
    ),
    "describer": TagGameProfile(
        key="describer",
        label="Describer",
        description="Read or hear a description and choose the matching image.",
        default_category="Reading",
        source_focus="sentences_reading",
        imported_from=["DescriberSetup32.0.1.rar"],
        default_settings={"choice_count": 4, "round_limit": 10, "prompt_source": "sentences_or_reading"},
    ),
    "bubbles_english": TagGameProfile(
        key="bubbles_english",
        label="Bubbles English",
        description="Bubble-style tap game for quick vocabulary recognition with bright arcade visuals.",
        default_category="Vocabulary",
        source_focus="vocab_audio",
        imported_from=["BubblesEnglishSetup32.0.1.rar"],
        default_settings={"choice_count": 6, "timer_seconds": 45, "bubble_mode": "image_text"},
    ),
    "spelling_bee": TagGameProfile(
        key="spelling_bee",
        label="Spelling Bee",
        description="Spell the target word from an image or audio prompt using a letter bank.",
        default_category="Phonics",
        source_focus="vocab_spelling",
        imported_from=["SpellingBeeSetup32.0.2.rar"],
        default_settings={"round_limit": 10, "max_word_length": 12, "show_hint": True},
    ),
    "hangman": TagGameProfile(
        key="hangman",
        label="Hangman",
        description="Guess letters to uncover the word before misses run out.",
        default_category="Phonics",
        source_focus="vocab_spelling",
        imported_from=["HangmanSetup32.0.1.rar"],
        default_settings={"round_limit": 10, "max_misses": 6, "show_translation": True},
    ),
    "falling_english": TagGameProfile(
        key="falling_english",
        label="Falling English",
        description="Timed tap-the-correct-item game with falling cards.",
        default_category="Vocabulary",
        source_focus="vocab_audio",
        imported_from=["FallingEnglishSetup32.0.1.rar"],
        default_settings={"timer_seconds": 45, "spawn_ms": 1300, "choice_count": 4},
    ),
    "fast_phrases": TagGameProfile(
        key="fast_phrases",
        label="Fast Phrases",
        description="Quick phrase and sentence rounds inspired by the portable content-folder game family.",
        default_category="Sentence Patterns",
        source_focus="sentences",
        imported_from=["FastPhrases2.1.rar"],
        default_settings={"timer_seconds": 60, "round_limit": 12, "token_source": "sentences"},
    ),
    "fast_english": TagGameProfile(
        key="fast_english",
        label="Fast English",
        description="Fast timed vocabulary rounds inspired by the portable myContent/settings.json game family.",
        default_category="Vocabulary",
        source_focus="vocab_audio",
        imported_from=["FastEnglish2.0.rar"],
        default_settings={"timer_seconds": 60, "round_limit": 15, "choice_count": 4},
    ),
}

GAME_LABELS: Dict[str, str] = {key: profile.label for key, profile in GAME_PROFILES.items()}

CATEGORY_SUGGESTIONS: List[str] = [
    "Vocabulary",
    "Body Parts",
    "Actions and Verbs",
    "School Objects",
    "Animals",
    "Food and Drink",
    "Prepositions and Place",
    "Grammar Connectors",
    "Sentence Patterns",
    "Reading",
    "Phonics",
    "Imported Game Families",
]


STYLE_LABELS: Dict[str, str] = {
    "sky_soft": "Sky Soft",
    "clean_light": "Clean Light",
    "white_minimal": "White Minimal",
    "bright_play": "Bright Play",
}


def ordered_game_types() -> List[str]:
    return [key for key in GAME_ORDER if key in GAME_PROFILES]


def get_game_profile(game_type: str) -> TagGameProfile:
    return GAME_PROFILES.get(game_type, GAME_PROFILES["touch_listen_cards"])


def default_settings_for_game(game_type: str) -> Dict[str, Any]:
    return dict(get_game_profile(game_type).default_settings)


def default_settings_json(game_type: str) -> str:
    return json.dumps(default_settings_for_game(game_type), ensure_ascii=False, indent=2)


def coerce_game_settings(game_type: str, raw: Any) -> Dict[str, Any]:
    base = default_settings_for_game(game_type)
    if isinstance(raw, dict):
        for key, value in raw.items():
            base[str(key)] = value
        return base
    if isinstance(raw, str) and raw.strip():
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            raise ValueError("Game options JSON must be an object.")
        for key, value in parsed.items():
            base[str(key)] = value
    return base
