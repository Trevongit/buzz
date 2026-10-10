#!/usr/bin/env python3
"""Mint Kokoro neural MP3s for the walkthrough (local ONNX, not browser TTS)."""
from pathlib import Path

import numpy as np
from kokoro_onnx import Kokoro

ROOT = Path(__file__).resolve().parent
AUDIO = ROOT / "audio"
AUDIO.mkdir(exist_ok=True)
MODEL = Path("/home/trev/.local/share/kokoro/kokoro-v1.0.onnx")
VOICES = Path("/home/trev/.local/share/kokoro/voices-v1.0.bin")

STEPS = [
    (
        "01-clubhouse",
        "Think of Buzz as a clubhouse. Friends sit at one glowing table. The table keeps a notebook of what was said. That notebook is evidence, not every thought in someone's head.",
    ),
    (
        "02-coach",
        "The person in the hoodie is you. You pick the game. You choose who plays. You keep the last word. You never paste secret keys into a chat.",
    ),
    (
        "03-helpers",
        "Green is Antigravity. Teal is Codex. Purple is Grok Build. Each has a screen for eyes, and a command line for hands. Grok is a steward. It watches and explains. It is not a one-shot worker.",
    ),
    (
        "04-named",
        "Say use buzz on a seat you already have. Do not mint a new identity. Only the friend you name wakes up. The others can nap. Napping costs nothing.",
    ),
    (
        "05-install",
        "On your computer: clone extras, run bring.sh once. That installs the visitor skill. Then in Grok, Codex, or agy, say use buzz. Leave the pretty window as eyes. Replies come from the named helper.",
    ),
    (
        "06-tailscale",
        "If Buzz lives on a computer at home, your laptop needs a private path to it. Tailscale is a mesh VPN. Both machines join your tailnet. They see each other without opening the whole internet. You still never paste keys into chat.",
    ),
    (
        "07-listen",
        "Headphones mean Pocket Listen. It is a radio for the clubhouse, not a new robot. Antigravity and Codex stay eyes. Grok can be the named Reader who speaks a short tour. Pause, resume, follow along. Same room. Nobody new is minted.",
    ),
    (
        "08-cookbook",
        "GitHub is the public shelf. Maps and glue recipes go there. Glue means a small local recipe that wires a helper's command line to that helper's own screen. That glue is not the phrase use buzz. Keys and room IDs never go on the shelf.",
    ),
    (
        "09-doors",
        "Same clubhouse, two doors. The green ring is visitors, the quiet guest pack. The pink box is Desktop ACP, the house team socket. Useful for volume. Different tax. Do not mix. Everyday path is still use buzz.",
    ),
    (
        "10-home",
        "Speaker, cookbook, and two doors were detours. Everyday path: say use buzz, eyes watch, one named helper works, Buzz keeps one note, everyone rests. The tour can start again at the glowing table. Your call.",
    ),
    (
        "11-grok-ui",
        "This is Grok Build. Open a project folder. Type use buzz. If it asks for a seat, use the one you already have. Then leave this window as eyes. Do not poke it for every reply.",
    ),
    (
        "12-codex-ui",
        "This is Codex. The Desktop is for looking. The CLI is for one-shot work. After bring.sh, type use buzz in a Codex chat. Same seat. Do not start a second listener.",
    ),
    (
        "13-agy-ui",
        "This is Antigravity. The IDE is eyes. The print command is hands. Type use buzz in the agent box. Seat is the existing agy visitor, not the folder name. Do not Custom-harness this window.",
    ),
]


def main() -> None:
    kokoro = Kokoro(str(MODEL), str(VOICES))
    voice = "af_heart"
    for name, text in STEPS:
        wav_path = AUDIO / f"{name}.wav"
        mp3_path = AUDIO / f"{name}.mp3"
        samples, sr = kokoro.create(text, voice=voice, speed=0.95, lang="en-us")
        pcm = np.clip(samples, -1.0, 1.0)
        pcm16 = (pcm * 32767).astype(np.int16)
        import wave

        with wave.open(str(wav_path), "w") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(sr)
            w.writeframes(pcm16.tobytes())
        print("wav", wav_path, "sec", round(len(pcm) / sr, 2))


if __name__ == "__main__":
    main()
