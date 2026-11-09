"""Resilient entry point for Scary Autopilot.

Uses the existing production pipeline, but provides a local story-writing fallback
when Gemini/Claude is unavailable or over quota. No API key is required for the
fallback. Video rendering and Edge TTS still need the runner's normal dependencies
and network access. Publishing still requires valid platform credentials.
"""
import json
import random
import re

import autopilot as app


def _make_story(fmt):
    """Create an original locally-generated horror story without a paid AI API."""
    seeds = [
        ("The Last Train to Bellweather", "a railway station that closed twenty years ago", "a conductor with no reflection"),
        ("The Room Behind the Wallpaper", "a rented house with one sealed bedroom", "a child humming through the wall"),
        ("The Voice in the Weather Radio", "a mountain town during a week of storms", "a broadcaster who knows tomorrow's names"),
        ("The House That Counted", "an isolated farmhouse beside a black forest", "footsteps that stop outside the door"),
        ("The Photograph at 3:17", "an old hotel where every clock stops at the same minute", "a figure appearing one step closer in every picture"),
        ("The Road That Wasn't There", "a country road missing from every map", "a passenger who remembers the narrator's childhood"),
    ]
    title, setting, presence = random.choice(seeds)
    names = ["Mara", "Elias", "June", "Thomas", "Nora", "Caleb"]
    narrator = random.choice(names)
    places = ["the north corridor", "the locked cellar", "the empty platform", "the upstairs landing", "the tree line"]
    sounds = ["three slow knocks", "a wet dragging sound", "a familiar voice whispering from the dark", "a clock ticking where no clock hung", "someone breathing in time with the narrator"]
    object_ = random.choice(["a brass key", "a cracked photograph", "a cassette tape", "a child-sized shoe", "a handwritten map"])
    clue = random.choice(["the date was tomorrow", "the handwriting was unmistakably theirs", "the face in the picture had their eyes", "the message described what they were doing at that exact moment", "the object was warm, as if someone had just held it"])
    opening = (
        f"The first warning came at 2:13 in the morning, when {narrator} heard "
        f"{random.choice(sounds)} coming from {random.choice(places)}. "
        f"It should have been impossible. {setting.capitalize()} had been quiet for years, "
        f"and everyone nearby knew the story of {presence}. "
    )
    short_body = [
        f"{narrator} switched on every light and checked the doors. They were locked from the inside. "
        f"On the kitchen table sat {object_}, although it had not been there before. ",
        f"When they picked it up, they discovered that {clue}. A phone rang in the next room. "
        f"The caller ID showed their own number. ",
        f"They answered. At first there was only static. Then their own voice whispered, "
        f"\"Do not look behind you. I am still trying to get out.\" ",
        f"The lights went dark. Something crossed the hallway without making a sound. "
        f"{narrator} ran for the front door, but the lock turned by itself. ",
        f"At dawn, the neighbours found the house empty. The only thing left was a new photograph "
        f"on the table. It showed {narrator} standing at the window, looking out. "
        f"Behind the glass, someone identical was smiling. ",
    ]
    if fmt == "short":
        narration = opening + "".join(short_body)
        words = narration.split()
        if len(words) > 150:
            narration = " ".join(words[:150])
        elif len(words) < 120:
            narration += " The photograph was still warm. On its back, a final sentence had appeared: "
            narration += "\"You heard me. Now let me in.\""
        return {
            "title": title,
            "description": "An original atmospheric horror story. Listen closely, and watch the final detail.",
            "tags": ["horror", "scary story", "creepy", "mystery", "shorts"],
            "narration": narration,
            "visual_keywords": ["empty railway station at night", "foggy house exterior", "dark hallway", "rain on window", "old photograph", "flickering light", "misty forest", "abandoned room"],
        }

    # A longer three-act story. Each beat advances the mystery instead of padding
    # with duplicated paragraphs, while remaining deterministic enough to narrate.
    beats = [
        "At first, the explanation seemed ordinary. Old buildings settle, pipes complain, and tired minds turn harmless sounds into warnings. That was what the neighbours said, although none of them would meet {n}'s eyes.",
        "The next evening, the sound returned from {place}. It came in a patient rhythm, always stopping when {n} moved toward it. When {n} stepped away, it began again, a little closer than before.",
        "A search of the room revealed {obj}. Dust covered everything around it, except for a clean outline where it had been waiting. The small discovery made the whole place feel recently occupied.",
        "Inside was a note with no greeting and no signature. It contained only this sentence: {clue}. The paper smelled of rain, even though every window had been shut.",
        "That night, {n} called the one person who might understand. The call connected, but the voice on the other end sounded distant, as if speaking from the bottom of a well. It asked why the lights were on.",
        "Before an answer came, the voice described the room in exact detail: the chair, the curtain, the narrow crack above the door. Then it described a shadow standing behind {n}.",
        "There was nobody there when {n} turned. Yet the curtain moved against the direction of the wind, and the floorboards made the unmistakable sound of someone taking one careful step.",
        "The following morning brought a new discovery. A hidden panel behind the cupboard opened onto a narrow space that should not have fit inside the wall. The air within it was cold and smelled of wet earth.",
        "On the inner surface, hundreds of small marks had been scratched into the wood. They formed columns, each ending with a date. The final date was the day after tomorrow.",
        "A sound came from the space. It was not a knock this time. It was {sound}, followed by a voice repeating {n}'s name with the patience of someone who had waited a very long time.",
        "The sensible choice was to leave. {n} packed a bag, walked to the car, and drove toward the main road. Every turn brought the same crooked tree and the same broken sign back into view.",
        "After the fourth loop, the radio switched on by itself. A presenter calmly announced the time, then described a person walking beside the road. The description matched {n}'s clothes exactly.",
        "The road ended at the front gate. The house stood dark, but an upstairs window glowed. A silhouette waited behind the glass, holding something that looked like {obj}.",
        "Inside, the clock had stopped. The hidden panel stood open. The marks on the wood had changed, and one fresh line had appeared beneath the final date. It contained {clue}.",
        "A memory returned then, sharp and unwelcome: a childhood promise, a door that should never have been opened, and a voice that had once begged to be remembered.",
        "The presence did not chase. It did not need to. It moved through the walls, making the house seem to breathe. Every room became a little smaller, every exit a little farther away.",
        "At the centre of the hallway lay a photograph. In it, {n} stood beside a second figure whose face had been scratched away. On the back was a message written in fresh ink.",
        "The message explained the marks. They were not a count of days. They were a count of attempts. Each line recorded another time someone had tried to leave, and every line ended in the same place.",
        "A whisper came from the sealed room. It used a voice {n} recognised, a voice that belonged to someone who had been gone for years. It asked to be let out just once.",
        "For the first time, the house became completely silent. Even the rain stopped. {n} understood that the silence was not an absence. It was the moment before an answer.",
        "The door opened a fraction. Beyond it was not a bedroom, but the same hallway seen from the other end. A figure stood there, holding its hand against the wood.",
        "It looked almost like {n}. The difference was small: a stillness in the eyes, and a smile that arrived before the face had reason to smile.",
        "The figure spoke without moving its lips. It said the house had never been keeping anyone inside. It had been keeping something else from getting out.",
        "The floor trembled. The lights flickered once, then steadied. In the photograph, the scratched-out face began to clear, revealing the same expression now waiting in the doorway.",
        "There was one way to stop it, the note suggested: never answer when it used a familiar voice. Never follow it when it called from a place you could not see.",
        "Then the voice came from behind {n}, soft and exhausted. It sounded exactly like the person {n} had missed most. It said, please, I am frightened.",
        "The hand reached for the door. {n} stepped back instead. The figure's smile disappeared, and for a moment it looked genuinely afraid. That was the most frightening thing of all.",
        "The house gave a long settling groan. Somewhere deep inside the walls, something ran toward the sealed room. The door slammed, and the marks on the panel vanished one by one.",
        "At sunrise, the neighbours found the front door open. The rooms were empty, the clocks were running, and the hidden panel had become an ordinary section of wall.",
        "Only one object remained on the table: {obj}. Beside it lay a photograph of the empty house, taken from the road. In an upstairs window, a small figure watched the camera.",
        "The neighbours agreed that the house was finally quiet. They sold it months later, and the new owners painted every room white. Nobody mentioned the old marks.",
        "On the first night, the new owner heard three slow knocks from inside the wall. A voice whispered a name that did not belong to anyone in the family.",
        "The owner called the estate agent. The line rang once, twice, then connected to a voice that sounded tired and very far away. It said the house had been waiting for them.",
        "By morning, the owner had left. The furniture remained, the doors were locked, and the photograph on the table had changed. There were now two figures in the upstairs window.",
        "The second figure stood behind the first with one hand raised, as if asking the viewer to come closer. On the back, in handwriting nobody recognised, were five words: do not answer the next knock.",
    ]
    paragraphs = []
    for i, beat in enumerate(beats):
        paragraphs.append(beat.format(n=narrator, place=random.choice(places), obj=object_, clue=clue, sound=random.choice(sounds)))
    narration = opening + "\n\n" + "\n\n".join(paragraphs)
    return {
        "title": title,
        "description": "An original slow-burn horror story about a place that remembers everyone who enters.",
        "tags": ["horror", "scary story", "creepy story", "mystery", "dark fiction"],
        "narration": narration,
        "visual_keywords": ["abandoned house at night", "foggy forest road", "dark hallway", "old photograph", "rain covered window", "dusty hidden room", "flickering light", "empty country road"],
    }


def _local_ai(system, prompt, max_tokens=4000, json_mode=False):
    # write_script and its optional polish pass both request the same JSON shape.
    if "Reply with ONLY a JSON object" in prompt or "Improve this short horror script" in prompt:
        fmt = "short" if "SHORT vertical video" in prompt or "short horror script" in prompt else "long"
        return json.dumps(_make_story(fmt), ensure_ascii=False)
    return "Use a clear hook, escalating suspense, original characters, atmospheric settings, and a memorable final twist."


def _local_research(fmt, hist):
    return (
        "Local fallback: use an immediate curiosity hook, a specific unsettling setting, "
        "short spoken sentences, escalating clues, atmospheric visuals, and a final reveal. "
        "Create an original plot; do not imitate existing videos."
    )


# Prefer the configured AI provider. If it times out, is over quota, or is
# unavailable, fall back to local original-story generation so a run can continue.
_network_ai = app.ask_ai
_network_research = app.research

def _resilient_ai(system, prompt, max_tokens=4000, json_mode=False):
    try:
        return _network_ai(system, prompt, max_tokens=max_tokens, json_mode=json_mode)
    except Exception as exc:
        print("AI provider unavailable; using local story fallback:", str(exc)[:300])
        return _local_ai(system, prompt, max_tokens=max_tokens, json_mode=json_mode)

def _resilient_research(fmt, hist):
    try:
        return _network_research(fmt, hist)
    except Exception as exc:
        print("Research unavailable; using local guidance:", str(exc)[:300])
        return _local_research(fmt, hist)

app.ask_ai = _resilient_ai
app.research = _resilient_research

if __name__ == "__main__":
    app.main()
