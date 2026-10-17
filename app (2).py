import csv
import json
import threading
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

BASE_URL = "http://localhost:11434"
GENERATE_URL = f"{BASE_URL}/api/generate"
TAGS_URL = f"{BASE_URL}/api/tags"

APP_DIR = Path(__file__).parent
HISTORY_FILE = APP_DIR / "history.json"
PROFILE_FILE = APP_DIR / "profile.json"

DEFAULT_MODEL = "qwen2.5:3b"

TYPE_RULES = {
    "Menu Description": "Write 2-3 appetizing sentences for a menu. No hashtags.",
    "Instagram Caption": "Write a catchy caption under 60 words with 2-3 emojis and 5 relevant hashtags.",
    "Facebook Post": "Write a friendly post of 60-90 words with 2 emojis and a call to action to visit or order.",
    "WhatsApp Message": "Write a short message under 50 words with 1-2 emojis, ending with a call to action to order.",
    "Google Business Post": "Write a professional post of 50-80 words, no hashtags, mention the restaurant name.",
    "Special Offer": "Promote the dish. Only mention a discount or offer if it is given in Extra notes; otherwise do not invent one.",
}

TONES = {
    "Friendly": "warm and friendly",
    "Premium": "elegant and premium",
    "Fun": "playful and fun",
    "Desi/Street": "bold, desi street-food style with energy",
    "Family-friendly": "cozy and family-friendly",
}

LANGUAGES = {
    "English": "Write in English.",
}


FOREIGN_RANGES = [
    (0x0400, 0x04FF),  # Cyrillic
    (0x0600, 0x077F),  # Arabic / Urdu
    (0x0900, 0x097F),  # Devanagari
    (0x0A00, 0x0A7F),  # Gurmukhi
    (0x3040, 0x30FF),  # Japanese kana
    (0x4E00, 0x9FFF),  # Chinese
    (0xAC00, 0xD7AF),  # Korean
    (0xFB50, 0xFDFF),  # Arabic presentation forms
    (0xFE70, 0xFEFF),
]


def has_foreign_script(text):
    return any(lo <= ord(ch) <= hi for ch in text for lo, hi in FOREIGN_RANGES)


def load_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def save_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("green")

        self.title("MenuCraft AI - Restaurant Content Generator")
        self.geometry("940x840")
        self.minsize(800, 720)

        self.history = load_json(HISTORY_FILE, [])
        self.profile = load_json(PROFILE_FILE, {})
        self.stop_event = threading.Event()
        self.generating = False
        self.results = []

        self.build_ui()
        self.refresh_history_menu()
        threading.Thread(target=self.check_ollama, daemon=True).start()
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    # ---------- UI ----------
    def build_ui(self):
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.pack(fill="both", expand=True, padx=20, pady=16)

        ctk.CTkLabel(main, text="MenuCraft AI", font=("Segoe UI", 28, "bold")).pack(anchor="w")
        ctk.CTkLabel(
            main,
            text="Restaurant descriptions aur marketing content, open-source AI se, offline.",
            text_color="gray70",
        ).pack(anchor="w", pady=(0, 10))

        form = ctk.CTkFrame(main)
        form.pack(fill="x")
        form.columnconfigure(1, weight=1)
        form.columnconfigure(3, weight=1)

        self.restaurant_entry = self.add_entry(form, "Restaurant", 0, 0)
        self.restaurant_entry.insert(0, self.profile.get("restaurant", "My Restaurant"))
        self.dish_entry = self.add_entry(form, "Dish *", 0, 2)
        self.dish_entry.insert(0, "Chicken Burger")

        self.price_entry = self.add_entry(form, "Price", 1, 0)
        self.price_entry.insert(0, "Rs. 450")
        self.ingredients_entry = self.add_entry(form, "Ingredients", 1, 2)
        self.ingredients_entry.insert(0, "Chicken, lettuce, cheese, sauce")

        self.notes_entry = self.add_entry(form, "Extra notes", 2, 0)
        self.city_entry = self.add_entry(form, "City", 2, 2)
        self.city_entry.insert(0, self.profile.get("city", ""))

        self.type_box = self.add_menu(form, "Content type", list(TYPE_RULES), 3, 0)
        self.tone_box = self.add_menu(form, "Tone", list(TONES), 3, 2)
        self.tone_box.set(self.safe_choice(self.profile.get("tone"), TONES, "Friendly"))
        self.language_box = self.add_menu(form, "Language", list(LANGUAGES), 4, 0)
        self.language_box.set(self.safe_choice(self.profile.get("language"), LANGUAGES, "English"))
        self.model_box = self.add_menu(form, "Model", [DEFAULT_MODEL], 4, 2)
        self.model_box.set(self.profile.get("model", DEFAULT_MODEL))

        ctk.CTkLabel(form, text="Creativity").grid(row=5, column=0, sticky="w", padx=10, pady=8)
        self.temp_slider = ctk.CTkSlider(form, from_=0.1, to=1.2, number_of_steps=11)
        self.temp_slider.set(self.profile.get("temperature", 0.7))
        self.temp_slider.grid(row=5, column=1, columnspan=3, sticky="ew", padx=10, pady=8)

        buttons = ctk.CTkFrame(main, fg_color="transparent")
        buttons.pack(fill="x", pady=10)

        self.generate_button = ctk.CTkButton(buttons, text="Generate", width=110, command=self.start_single)
        self.generate_button.pack(side="left")
        self.stop_button = ctk.CTkButton(
            buttons, text="Stop", width=70, fg_color="#b33", hover_color="#822",
            state="disabled", command=self.stop_generate,
        )
        self.stop_button.pack(side="left", padx=6)
        self.csv_button = ctk.CTkButton(
            buttons, text="Menu CSV", width=100, fg_color="#2b6cb0", hover_color="#1e4e82",
            command=self.start_batch,
        )
        self.csv_button.pack(side="left")
        ctk.CTkButton(buttons, text="Copy", width=70, command=self.copy_content).pack(side="left", padx=6)
        ctk.CTkButton(buttons, text="Save .txt", width=85, command=self.save_txt).pack(side="left")
        ctk.CTkButton(buttons, text="Export CSV", width=95, command=self.export_csv).pack(side="left", padx=6)

        self.history_menu = ctk.CTkOptionMenu(
            buttons, values=["History"], width=210, command=self.load_history_item
        )
        self.history_menu.pack(side="right")

        self.status_label = ctk.CTkLabel(main, text="Ready", text_color="gray70")
        self.status_label.pack(anchor="w")

        self.output_box = ctk.CTkTextbox(main, wrap="word", font=("Segoe UI", 14))
        self.output_box.pack(fill="both", expand=True, pady=6)

    @staticmethod
    def safe_choice(value, options, default):
        return value if value in options else default

    def add_entry(self, parent, label, row, col):
        ctk.CTkLabel(parent, text=label).grid(row=row, column=col, sticky="w", padx=10, pady=6)
        entry = ctk.CTkEntry(parent)
        entry.grid(row=row, column=col + 1, sticky="ew", padx=10, pady=6)
        return entry

    def add_menu(self, parent, label, values, row, col):
        ctk.CTkLabel(parent, text=label).grid(row=row, column=col, sticky="w", padx=10, pady=6)
        menu = ctk.CTkOptionMenu(parent, values=values)
        menu.grid(row=row, column=col + 1, sticky="ew", padx=10, pady=6)
        return menu

    # ---------- Ollama ----------
    def check_ollama(self):
        try:
            with urllib.request.urlopen(TAGS_URL, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            models = [m["name"] for m in data.get("models", [])]
            if models:
                self.after(0, lambda: self.set_models(models))
            else:
                self.after(0, lambda: self.set_status("Ollama chal raha hai lekin koi model installed nahi."))
        except (urllib.error.URLError, OSError, json.JSONDecodeError):
            self.after(0, lambda: self.set_status("Ollama nahi mila. Ollama start karo, phir app dobara kholo."))

    def set_models(self, models):
        self.model_box.configure(values=models)
        if self.model_box.get() not in models:
            self.model_box.set(models[0])
        self.set_status(f"Ollama connected. {len(models)} model(s) mile.")

    # ---------- Prompt ----------
    def build_prompt(self, common, item):
        ctype = common["type"]
        return f"""You are a creative marketing writer for a small restaurant.
Restaurant: {common["restaurant"]}
City: {common["city"]}
Dish: {item["dish"]}
Menu category: {item.get("category", "Not provided")}
Price(s): {item["price"]}
Ingredients: {item["ingredients"]}
Extra notes: {item["notes"]}

Task: {ctype}
Rules: {TYPE_RULES[ctype]}
Tone: {TONES[common["tone"]]}.
Language: {LANGUAGES[common["language"]]}

Do not invent discounts, ingredients, awards or facts that are not listed above.
Return only the final content, with no explanations."""

    def read_common(self):
        return {
            "restaurant": self.restaurant_entry.get().strip() or "Our Restaurant",
            "city": self.city_entry.get().strip() or "Not provided",
            "type": self.type_box.get(),
            "tone": self.tone_box.get(),
            "language": self.language_box.get(),
            "model": self.model_box.get(),
            "temp": round(self.temp_slider.get(), 2),
        }

    # ---------- Start single / batch ----------
    def start_single(self):
        if self.generating:
            return
        dish = self.dish_entry.get().strip()
        if not dish:
            messagebox.showwarning("Missing information", "Dish ka naam likho.")
            return
        item = {
            "dish": dish,
            "price": self.price_entry.get().strip() or "Not provided",
            "ingredients": self.ingredients_entry.get().strip() or "Not provided",
            "notes": self.notes_entry.get().strip() or "None",
        }
        self.run_jobs(self.read_common(), [item])

    def start_batch(self):
        if self.generating:
            return
        path = filedialog.askopenfilename(
            title="Menu CSV chuno", filetypes=[("CSV file", "*.csv")]
        )
        if not path:
            return
        try:
            items = self.read_menu_csv(path)
        except (OSError, UnicodeDecodeError, csv.Error) as e:
            messagebox.showerror("CSV error", f"File nahi parhi ja saki.\n\n{e}")
            return
        if not items:
            messagebox.showwarning(
                "CSV khali hai",
                "Koi dish nahi mili. CSV mein 'dish' naam ka column hona chahiye.",
            )
            return
        if len(items) > 40:
            items = items[:40]
            messagebox.showinfo("Limit", "Pehli 40 dishes use hongi.")
        self.run_jobs(self.read_common(), items)

    @staticmethod
    def read_menu_csv(path):
        # Same dish on several rows (different sizes) becomes ONE item
        # with all sizes and prices combined.
        grouped = {}
        with open(path, newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                row = {
                    k.strip().lower(): v.strip()
                    for k, v in row.items()
                    if isinstance(k, str) and isinstance(v, str)
                }
                dish = row.get("dish") or row.get("name")
                if not dish:
                    continue
                category = row.get("category", "")
                entry = grouped.setdefault((category, dish), {
                    "dish": dish,
                    "category": category or "Not provided",
                    "prices": [],
                    "ingredients": row.get("ingredients") or "Not provided",
                    "notes": row.get("notes") or "None",
                })
                price = row.get("price", "")
                if price:
                    if not price.lower().startswith("rs"):
                        price = f"Rs. {price}"
                    size = row.get("size / type") or row.get("size") or ""
                    if size in ("-", "–", "—", "n/a", "N/A"):
                        size = ""
                    entry["prices"].append(f"{size}: {price}" if size else price)

        items = []
        for entry in grouped.values():
            entry["price"] = "; ".join(entry.pop("prices")) or "Not provided"
            items.append(entry)
        return items

    def run_jobs(self, common, items):
        self.generating = True
        self.stop_event.clear()
        self.generate_button.configure(state="disabled", text="Generating...")
        self.csv_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.output_box.delete("1.0", "end")
        self.set_status("AI content bana raha hai...")
        threading.Thread(target=self.worker, args=(common, items), daemon=True).start()

    # ---------- Worker ----------
    def stream_ollama(self, prompt, common):
        latin_only = common["language"] == "Roman Urdu"
        attempts = 3 if latin_only else 1
        text, bad = "", False
        for attempt in range(1, attempts + 1):
            text, bad = self.stream_once(prompt, common, live=not latin_only)
            if not bad or self.stop_event.is_set():
                break
            if attempt < attempts:
                self.after(0, self.set_status, f"Ghalat script aayi, dobara koshish ({attempt + 1}/{attempts})...")
        if latin_only:
            if bad:
                self.after(0, self.append_text, "[Roman Urdu nahi ban saki. Bara model (gpt-oss ya qwen2.5:7b) try karo.]")
                return ""
            self.after(0, self.append_text, text)
        return text

    def stream_once(self, prompt, common, live):
        num_predict = 1500 if "gpt-oss" in common["model"] else 400
        payload = {
            "model": common["model"],
            "prompt": prompt,
            "stream": True,
            "options": {"temperature": common["temp"], "num_predict": num_predict},
        }
        request = urllib.request.Request(
            GENERATE_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        parts = []
        bad = False
        with urllib.request.urlopen(request, timeout=300) as resp:
            for line in resp:
                if self.stop_event.is_set():
                    break
                line = line.strip()
                if not line:
                    continue
                chunk = json.loads(line.decode("utf-8"))
                token = chunk.get("response", "")
                if token:
                    if not live and has_foreign_script(token):
                        bad = True
                        break
                    parts.append(token)
                    if live:
                        self.after(0, self.append_text, token)
                if chunk.get("done"):
                    break
        return "".join(parts).strip(), bad

    def worker(self, common, items):
        error = None
        results = []
        total = len(items)
        try:
            for i, item in enumerate(items, 1):
                if self.stop_event.is_set():
                    break
                if total > 1:
                    self.after(0, self.append_text, f"=== {item['dish']} ({i}/{total}) ===\n")
                    self.after(0, self.set_status, f"{i}/{total} dishes: {item['dish']}...")
                text = self.stream_ollama(self.build_prompt(common, item), common)
                if total > 1:
                    self.after(0, self.append_text, "\n\n")
                if text:
                    results.append({
                        "dish": item["dish"],
                        "type": common["type"],
                        "tone": common["tone"],
                        "language": common["language"],
                        "model": common["model"],
                        "content": text,
                    })
        except urllib.error.HTTPError as e:
            error = f"Model error ({e.code}). Model installed hai? 'ollama list' check karo."
        except urllib.error.URLError:
            error = "Ollama se connection nahi hua. Ollama chal raha hai?"
        except TimeoutError:
            error = "Time out ho gaya. Chota model try karo."
        except json.JSONDecodeError:
            error = "Ollama ka jawab samajh nahi aya."
        self.after(0, self.finish_generate, results, error)

    def append_text(self, token):
        self.output_box.insert("end", token)
        self.output_box.see("end")

    def finish_generate(self, results, error):
        self.generating = False
        self.generate_button.configure(state="normal", text="Regenerate")
        self.csv_button.configure(state="normal")
        self.stop_button.configure(state="disabled")
        self.results = results
        if error:
            self.set_status("Kuch masla hua.")
            messagebox.showerror("AI Error", error)
        if results:
            self.add_history(results)
            if not error:
                self.set_status(f"Tayyar! {len(results)} content bana. Export CSV se save kar sakte ho.")
        elif not error:
            self.set_status("Koi content nahi aya.")

    def stop_generate(self):
        self.stop_event.set()
        self.set_status("Rok diya gaya.")

    # ---------- History / export ----------
    def add_history(self, results):
        text = self.output_box.get("1.0", "end").strip()
        first = results[0]
        dish = first["dish"] if len(results) == 1 else f"Menu ({len(results)} dishes)"
        item = {
            "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "dish": dish,
            "type": first["type"],
            "language": first["language"],
            "text": text,
        }
        self.history.insert(0, item)
        self.history = self.history[:50]
        save_json(HISTORY_FILE, self.history)
        self.refresh_history_menu()

    @staticmethod
    def history_label(item):
        return f'{item["time"]} | {item["dish"]} | {item["type"]}'

    def refresh_history_menu(self):
        labels = [self.history_label(i) for i in self.history] or ["History"]
        self.history_menu.configure(values=labels)
        self.history_menu.set("History")

    def load_history_item(self, label):
        for item in self.history:
            if self.history_label(item) == label:
                self.output_box.delete("1.0", "end")
                self.output_box.insert("end", item["text"])
                self.set_status("Purana content load hua.")
                break

    def copy_content(self):
        content = self.output_box.get("1.0", "end").strip()
        if content:
            self.clipboard_clear()
            self.clipboard_append(content)
            self.set_status("Copy ho gaya!")

    def save_txt(self):
        content = self.output_box.get("1.0", "end").strip()
        if not content:
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".txt", filetypes=[("Text file", "*.txt")]
        )
        if path:
            Path(path).write_text(content, encoding="utf-8")
            self.set_status("Text file save ho gayi.")

    def export_csv(self):
        if not self.results:
            messagebox.showinfo("Export", "Pehle content generate karo.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv", filetypes=[("CSV file", "*.csv")]
        )
        if not path:
            return
        fields = ["dish", "type", "tone", "language", "model", "content"]
        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=fields)
                writer.writeheader()
                writer.writerows(self.results)
            self.set_status("CSV save ho gayi. Excel mein khol sakte ho.")
        except OSError as e:
            messagebox.showerror("Export error", f"File save nahi hui.\n\n{e}")

    # ---------- Helpers ----------
    def set_status(self, text):
        self.status_label.configure(text=text)

    def on_close(self):
        save_json(PROFILE_FILE, {
            "restaurant": self.restaurant_entry.get().strip(),
            "city": self.city_entry.get().strip(),
            "tone": self.tone_box.get(),
            "language": self.language_box.get(),
            "model": self.model_box.get(),
            "temperature": round(self.temp_slider.get(), 2),
        })
        self.stop_event.set()
        self.destroy()


if __name__ == "__main__":
    App().mainloop()
