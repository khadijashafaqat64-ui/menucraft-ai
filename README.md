# MenuCraft AI

A desktop app that writes menu descriptions and social media content for small restaurants, cafes and home kitchens. It runs entirely on your own computer with an open-weight model through [Ollama](https://ollama.com), so it works offline, has no per-use cost, and keeps menu and pricing data private.

Built for the Hacktoberfest Open-Source AI Challenge, Week 2: Side Hustle.

## Features

- **Six content types:** menu description, Instagram caption, Facebook post, WhatsApp message, Google Business post, special offer
- **Five tones:** friendly, premium, fun, desi/street, family-friendly, plus a creativity slider
- **Whole menu from a CSV:** generate content for every dish in one click. Rows that belong to the same dish (for example one pizza in four sizes) are merged into a single item with all sizes and prices
- **Live streaming output** with a Stop button
- **Model dropdown:** every model installed in Ollama shows up automatically
- **History** of the last 50 generations, and a saved restaurant profile
- **Export** results to CSV (opens in Excel) or save as a text file
- **Guardrails:** the prompt tells the model not to invent discounts, ingredients or awards

## Requirements

- Python 3.10 or newer
- [Ollama](https://ollama.com) installed and running
- A model pulled in Ollama, for example `qwen2.5:3b` (about 1.9 GB)

## Setup

```bash
# 1. Get a model
ollama pull qwen2.5:3b

# 2. Install the one Python dependency
pip install -r requirements.txt

# 3. Run the app
python app.py
```

When the app starts, the status line should say that Ollama is connected and how many models it found.

## Using a menu CSV

Click **Menu CSV** and choose your file. The only required column is `dish` (or `name`). All other columns are optional:

| Column | Meaning |
|---|---|
| `dish` | Dish name (required) |
| `price` | Price. `Rs.` is added if missing |
| `size / type` or `size` | Size or variant, merged with the price |
| `category` | Menu section, for example STARTERS |
| `ingredients` | Used in the prompt. The model is told not to invent ingredients |
| `notes` | Extra notes, such as an offer. The special offer type only mentions offers written here |

See `menu.csv` for an example. Up to 40 dishes are processed per run.

## Limitations

- **English only.** I first added Urdu and Roman Urdu, but the 3B model mixed in other scripts and produced broken sentences, so I removed them. A larger local model may do better.
- Output quality depends on the model you choose. The default 3B model is small so it runs on ordinary laptops.
- The app is a single-file prototype and has no automated tests.

## Privacy

Everything runs locally and the app only talks to Ollama on `localhost:11434`. History and profile are stored in `history.json` and `profile.json` next to the app, and are not uploaded anywhere.

## Tech stack

Python, CustomTkinter, Ollama, Qwen 2.5 (3B).

## License

Add a license of your choice (for example MIT) before sharing the code.
