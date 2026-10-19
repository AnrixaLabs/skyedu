from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List


TEXT_EXCLUSION_TOKENS = [
    "text",
    "letters",
    "numbers",
    "english text",
    "chinese characters",
    "caption",
    "label",
    "subtitle",
    "watermark",
    "logo",
    "signboard",
    "poster writing",
    "book cover text",
    "blackboard writing",
    "handwriting",
]

POS_PREFIX_RE = re.compile(r"^(noun|verb|adjective|adverb|preposition|prep|phrase|expression|time|pronoun|question_word|question word|number|determiner)\s*:\s*", re.IGNORECASE)

PREPOSITION_SCENES = {
    "on": "a small red ball on a wooden table, clear spatial relation, simple educational scene, plain background",
    "in": "a small red ball inside an open box, clear spatial relation, simple educational scene, plain background",
    "under": "a small red ball under a chair, clear spatial relation, simple educational scene, plain background",
    "behind": "a small red ball behind a table, clear spatial relation, simple educational scene, plain background",
    "in front of": "a small red ball in front of a box, clear spatial relation, simple educational scene, plain background",
    "next to": "a small red ball next to a chair, clear spatial relation, simple educational scene, plain background",
    "between": "a small red ball between two chairs, clear spatial relation, simple educational scene, plain background",
}

VERB_SCENES = {
    "get up": "a child getting out of bed in the morning, clear daily routine action, simple bedroom scene",
    "wash my face": "a child washing their face at a sink, clear daily routine action, simple bathroom scene",
    "brush my teeth": "a child brushing teeth with a toothbrush at a sink, clear daily routine action",
    "play games": "a child happily playing a simple game with toys, clear action, no screen text",
    "go to school": "a child walking to school with a schoolbag, clear school routine action",
    "do homework": "a child doing homework at a desk with notebook and pencil, clear school routine action",
    "carry": "a child carrying a schoolbag and books, clear action",
    "finish": "a child finishing homework at a desk, workbook and pencil visible, clear completed task",
    "visit": "a child visiting grandparents or friends at home, greeting scene, clear social action",
    "read": "a child reading a book, clear action, simple study scene",
    "write": "a child writing in a notebook with a pencil, clear action",
    "draw": "a child drawing a picture with crayons or pencils, clear action",
    "run": "a child running outdoors, clear body action, simple background",
    "jump": "a child jumping, clear body action, simple background",
}

QUESTION_WORD_SCENES = {
    "who": "two children and one teacher in a classroom, one person highlighted by focus and pointing gesture, clear people-identification scene",
    "where": "a schoolbag placed in one obvious location in a room, clear location-question scene",
    "what": "one child pointing to a single obvious object on a desk, clear object-identification scene",
    "when": "a child looking at a clock in a simple daily routine scene, clear time-question scene",
    "which": "two obvious choices side by side with one choice highlighted by pointing gesture, clear selection scene",
    "whose": "two children with one named item belonging clearly to one child, clear ownership scene",
    "how": "a child showing a simple way to do something, clear process scene",
    "why": "a child asking a question about a simple cause-and-effect scene, clear reason scene",
}

PRONOUN_SCENES = {
    "he": "a single boy standing and being pointed at, clear pronoun reference scene",
    "she": "a single girl standing and being pointed at, clear pronoun reference scene",
    "they": "two or three children together being pointed at, clear plural pronoun scene",
    "we": "a teacher and child together smiling toward the viewer, clear inclusive pronoun scene",
    "it": "a single obvious object being pointed at, clear object-reference scene",
}

COLOR_SCENES = {
    "red": "a bright red t-shirt on one child, simple clean background",
    "blue": "a bright blue t-shirt on one child, simple clean background",
    "green": "a bright green backpack, simple clean background",
    "yellow": "a bright yellow raincoat on one child, simple clean background",
    "black": "a black school shoe or black backpack, simple clean background",
    "white": "a white shirt on one child, simple clean background",
    "brown": "a brown teddy bear or brown school shoe, simple clean background",
    "pink": "a pink schoolbag or pink t-shirt, simple clean background",
    "purple": "a purple pencil case or purple t-shirt, simple clean background",
    "orange": "an orange t-shirt or orange balloon, simple clean background",
}

NUMBER_SCENES = {
    "0": "an empty counting tray with zero apples, simple educational counting scene",
    "1": "one apple on a plain table, clear counting scene",
    "2": "two apples side by side on a plain table, clear counting scene",
    "3": "three apples grouped clearly on a plain table, clear counting scene",
    "4": "four apples grouped clearly on a plain table, clear counting scene",
    "5": "five apples grouped clearly on a plain table, clear counting scene",
    "6": "six pencils grouped clearly, clear counting scene",
    "7": "seven stars or seven blocks grouped clearly, clear counting scene",
    "8": "eight crayons grouped clearly, clear counting scene",
    "9": "nine balls grouped clearly, clear counting scene",
    "10": "ten apples grouped clearly on a plain table, clear counting scene",
    "11": "eleven apples grouped clearly on a plain table, clear counting scene",
    "12": "twelve apples grouped clearly on a plain table, clear counting scene",
    "20": "twenty simple counting objects arranged in two neat rows, clear counting scene",
}

EMOTION_ADJECTIVES = {
    "happy", "sad", "angry", "scared", "afraid", "tired", "busy", "excited", "hungry", "thirsty",
}

VISUAL_ATTRIBUTE_ADJECTIVES = {
    "big", "small", "tall", "short", "hot", "cold", "fast", "slow", "clean", "dirty", "full", "empty",
    "open", "closed", "new", "old", "long", "young", "heavy", "light",
    "red", "blue", "green", "yellow", "black", "white", "brown", "pink", "purple", "orange",
}

IRREGULAR_COMPARATIVES = {
    "better": "good", "worse": "bad", "bigger": "big", "smaller": "small", "taller": "tall", "shorter": "short",
    "faster": "fast", "slower": "slow", "hotter": "hot", "colder": "cold", "cleaner": "clean", "dirtier": "dirty",
    "older": "old", "newer": "new", "longer": "long", "younger": "young", "happier": "happy", "sadder": "sad",
    "heavier": "heavy", "lighter": "light",
}

IRREGULAR_SUPERLATIVES = {
    "best": "good", "worst": "bad", "biggest": "big", "smallest": "small", "tallest": "tall", "shortest": "short",
    "fastest": "fast", "slowest": "slow", "hottest": "hot", "coldest": "cold", "cleanest": "clean", "dirtiest": "dirty",
    "oldest": "old", "newest": "new", "longest": "long", "youngest": "young", "happiest": "happy", "saddest": "sad",
    "heaviest": "heavy", "lightest": "light",
}

NON_VISUAL_FALLBACK = {"a", "an", "the", "and", "or", "but", "because", "if", "then", "than", "of", "for"}


@dataclass(slots=True)
class VisualPlan:
    clean_word: str
    render_mode: str
    scene_type: str
    scene: str
    include: List[str] = field(default_factory=list)
    exclude: List[str] = field(default_factory=list)
    fallback_label: str = ""


def clean_visual_label(raw: str) -> str:
    text = (raw or "").strip()
    text = POS_PREFIX_RE.sub("", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalized_visual_key(raw: str) -> str:
    return clean_visual_label(raw).strip().lower()


def is_comparative(word: str) -> bool:
    w = normalized_visual_key(word)
    return w in IRREGULAR_COMPARATIVES or (len(w) > 4 and w.endswith("er"))


def is_superlative(word: str) -> bool:
    w = normalized_visual_key(word)
    return w in IRREGULAR_SUPERLATIVES or (len(w) > 5 and w.endswith("est"))


def comparative_base(word: str) -> str:
    w = normalized_visual_key(word)
    if w in IRREGULAR_COMPARATIVES:
        return IRREGULAR_COMPARATIVES[w]
    if w.endswith("ier") and len(w) > 4:
        return w[:-3] + "y"
    if w.endswith("er") and len(w) > 4:
        return w[:-3] if len(w) >= 5 and w[-3] == w[-4] else w[:-2]
    return w


def superlative_base(word: str) -> str:
    w = normalized_visual_key(word)
    if w in IRREGULAR_SUPERLATIVES:
        return IRREGULAR_SUPERLATIVES[w]
    if w.endswith("iest") and len(w) > 5:
        return w[:-4] + "y"
    if w.endswith("est") and len(w) > 5:
        return w[:-4] if len(w) >= 6 and w[-4] == w[-5] else w[:-3]
    return w


def _comparison_scene(base: str, target_word: str, level: str) -> str:
    anchor = "ball" if base in {"big", "small", "bigger", "smaller", "biggest", "smallest"} else "child"
    if base in {"big", "small"}:
        if level == "comparative":
            return f"two {anchor}s side by side, one clearly {target_word} than the other, strong educational size comparison, plain background"
        return f"three {anchor}s side by side, one clearly the {target_word}, strong educational size comparison, plain background"
    if level == "comparative":
        return f"two child-friendly objects or characters side by side, one clearly {target_word} than the other, strong educational comparison, plain background"
    return f"three child-friendly objects or characters side by side, one clearly the {target_word}, strong educational comparison, plain background"


def _number_scene(key: str) -> str:
    if key in NUMBER_SCENES:
        return NUMBER_SCENES[key]
    if key.isdigit():
        return f"{key} simple counting objects arranged clearly, plain background, educational counting scene"
    return f"clear educational counting scene for {key}, plain background, no written digits"


def resolve_visual_plan(word: str, pos: str, zh: str = "", example_en: str = "") -> VisualPlan:
    clean = clean_visual_label(word)
    key = normalized_visual_key(word)
    pos = (pos or "noun").strip().lower() or "noun"
    fallback_label = f"{clean} · {zh}" if zh else clean
    exclude = list(TEXT_EXCLUSION_TOKENS)

    if key in NON_VISUAL_FALLBACK:
        return VisualPlan(
            clean_word=clean,
            render_mode="symbolic_card",
            scene_type="non_visual_symbolic_fallback",
            scene=f"simple child-friendly symbolic icon for the concept '{clean}', plain background, no text",
            include=[clean, "simple symbol", "plain background"],
            exclude=exclude + ["school poster", "label", "blackboard"],
            fallback_label=fallback_label,
        )

    if pos == "preposition" or key in PREPOSITION_SCENES:
        scene = PREPOSITION_SCENES.get(key, f"objects arranged to clearly show the relation '{clean}', simple educational relation scene, plain background")
        return VisualPlan(
            clean_word=clean,
            render_mode="relation_scene",
            scene_type="position_relation_scene",
            scene=scene,
            include=[clean, "clear relation", "simple objects", "plain background"],
            exclude=exclude + ["crowded classroom", "poster", "labels on objects"],
            fallback_label=fallback_label,
        )

    if pos == "question_word" or key in QUESTION_WORD_SCENES:
        return VisualPlan(
            clean_word=clean,
            render_mode="guided_scene",
            scene_type="question_word_scene",
            scene=QUESTION_WORD_SCENES.get(key, f"clear child-friendly scene that explains the question word '{clean}', plain background"),
            include=[clean, "clear question context", "plain background"],
            exclude=exclude + ["speech bubble text", "blackboard text", "floating labels"],
            fallback_label=fallback_label,
        )

    if pos == "pronoun" or key in PRONOUN_SCENES:
        return VisualPlan(
            clean_word=clean,
            render_mode="guided_scene",
            scene_type="pronoun_reference_scene",
            scene=PRONOUN_SCENES.get(key, f"clear child-friendly reference scene for pronoun '{clean}', plain background"),
            include=[clean, "clear reference", "plain background"],
            exclude=exclude + ["speech bubble text", "floating labels"],
            fallback_label=fallback_label,
        )

    if pos == "number" or key.isdigit():
        return VisualPlan(
            clean_word=clean,
            render_mode="counting_scene",
            scene_type="number_counting_scene",
            scene=_number_scene(key),
            include=[clean, "clear grouped objects", "plain background"],
            exclude=exclude + ["written digits", "flashcards", "poster numbers"],
            fallback_label=fallback_label,
        )

    if is_superlative(clean):
        base = superlative_base(clean)
        return VisualPlan(
            clean_word=clean,
            render_mode="contrast_pair",
            scene_type="superlative_comparison_scene",
            scene=_comparison_scene(base, clean, "superlative"),
            include=[clean, "three items", "clear comparison"],
            exclude=exclude + ["single object only", "ambiguous size relation"],
            fallback_label=fallback_label,
        )

    if is_comparative(clean):
        base = comparative_base(clean)
        return VisualPlan(
            clean_word=clean,
            render_mode="contrast_pair",
            scene_type="comparative_comparison_scene",
            scene=_comparison_scene(base, clean, "comparative"),
            include=[clean, "two items", "clear comparison"],
            exclude=exclude + ["single object only", "ambiguous size relation"],
            fallback_label=fallback_label,
        )

    if pos in {"verb", "phrase"}:
        scene = VERB_SCENES.get(key, f"a child clearly performing the action '{clean}', simple educational action scene, plain background")
        return VisualPlan(
            clean_word=clean,
            render_mode="action_scene",
            scene_type="literal_action_scene",
            scene=scene,
            include=[clean, "child", "clear action", "plain background"],
            exclude=exclude + ["still life", "isolated object only", "decorative scene"],
            fallback_label=fallback_label,
        )

    if pos == "adjective":
        if key in EMOTION_ADJECTIVES:
            return VisualPlan(
                clean_word=clean,
                render_mode="attribute_scene",
                scene_type="emotion_state_scene",
                scene=f"a child clearly showing the feeling '{clean}' through facial expression and body language, simple educational scene, plain background",
                include=[clean, "child", "clear face expression", "plain background"],
                exclude=exclude + ["empty desk", "objects only", "no person"],
                fallback_label=fallback_label,
            )
        if key in COLOR_SCENES:
            return VisualPlan(
                clean_word=clean,
                render_mode="attribute_scene",
                scene_type="color_attribute_scene",
                scene=COLOR_SCENES[key],
                include=[clean, "single clear colored object", "plain background"],
                exclude=exclude + ["many colors equally strong", "written color names", "rainbow poster"],
                fallback_label=fallback_label,
            )
        if key in VISUAL_ATTRIBUTE_ADJECTIVES:
            return VisualPlan(
                clean_word=clean,
                render_mode="attribute_scene",
                scene_type="visible_attribute_scene",
                scene=f"a single child-friendly object or character that is clearly '{clean}', simple educational scene, plain background",
                include=[clean, "single obvious concept", "plain background"],
                exclude=exclude + ["ambiguous attribute", "crowded scene"],
                fallback_label=fallback_label,
            )
        return VisualPlan(
            clean_word=clean,
            render_mode="attribute_scene",
            scene_type="adjective_scene",
            scene=f"a child-friendly scene that clearly shows the meaning '{clean}', simple educational scene, plain background",
            include=[clean, "clear meaning", "plain background"],
            exclude=exclude + ["abstract art", "symbolic substitution"],
            fallback_label=fallback_label,
        )

    if pos == "time":
        return VisualPlan(
            clean_word=clean,
            render_mode="attribute_scene",
            scene_type="time_context_scene",
            scene=f"a child-friendly daily life scene that clearly represents '{clean}', simple educational context, plain background",
            include=[clean, "daily life", "plain background"],
            exclude=exclude + ["clock face only", "calendar text", "numbers"],
            fallback_label=fallback_label,
        )

    return VisualPlan(
        clean_word=clean,
        render_mode="single_object",
        scene_type="literal_object_scene",
        scene=f"a clear educational illustration showing '{clean}', single obvious concept, plain background",
        include=[clean, "single obvious concept", "plain background"],
        exclude=exclude + ["decorative text", "poster", "label"],
        fallback_label=fallback_label,
    )
