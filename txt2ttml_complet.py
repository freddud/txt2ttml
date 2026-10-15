# app.py
# Streamlit UI + converter (single-file)
# Run:  pip install streamlit
#       streamlit run app.py

import re
import html
import streamlit as st


def txt_to_ttml(
    raw: str,
    *,
    split_mode: str = "blank_lines",  # "blank_lines" or "each_line"
    rate_mode: str = "WPM",           # "WPM" or "CPS"
    wpm: float = 160.0,
    cps: float = 17.0,
    gap: float = 1.0,
    lang: str = "fr",
    max_dur: float = 30.0,            # you wanted 30s max
) -> str:
    """
    Convert text to TTML with estimated timecodes.
    - split_mode:
        - "blank_lines": 1 paragraph (separated by blank line) = 1 cue
        - "each_line": 1 non-empty line = 1 cue
    - rate_mode:
        - "WPM": duration = word_count / WPM * 60
        - "CPS": duration = char_count / CPS
    """

    # Normalize line endings (Windows/Mac/old Mac)
    raw = raw.replace("\r\n", "\n").replace("\r", "\n")

    def fmt_time(t: float) -> str:
        h = int(t // 3600); t -= h * 3600
        m = int(t // 60);   t -= m * 60
        s = int(t)
        ms = int(round((t - s) * 1000))
        if ms == 1000:
            s += 1
            ms = 0
        return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"

    def word_count(text: str) -> int:
        return len(re.findall(r"\b[\w’']+\b", text, flags=re.UNICODE))

    def char_count(text: str) -> int:
        # "useful" char count for CPS (collapse whitespace)
        t = re.sub(r"\s+", " ", text).strip()
        return len(t)

    # --- split into cues ---
    if split_mode == "each_line":
        units = [ln.strip() for ln in raw.split("\n") if ln.strip()]
    else:
        units = [p.strip() for p in re.split(r"\n\s*\n+", raw) if p.strip()]

    # --- build TTML <p> ---
    t = 0.0
    body = []

    for i, u in enumerate(units, start=1):
        clean = re.sub(r"\s+", " ", u).strip()

        if rate_mode.upper() == "CPS":
            n = char_count(clean)
            dur = (n / cps) if n else 1.0
        else:
            n = word_count(clean)
            dur = (n / wpm) * 60.0 if n else 1.0

        # safeguards
        dur = max(1.0, min(dur, max_dur))

        begin = t
        end = t + dur
        t = end + gap

        text = html.escape(clean)
        body.append(
            f'      <p xml:id="p{i}" begin="{fmt_time(begin)}" end="{fmt_time(end)}">{text}</p>'
        )

    return f'''<?xml version="1.0" encoding="UTF-8"?>
<tt xmlns="http://www.w3.org/ns/ttml"
    xmlns:tts="http://www.w3.org/ns/ttml#styling"
    xmlns:ttm="http://www.w3.org/ns/ttml#metadata"
    xml:lang="{html.escape(lang)}">
  <head>
    <styling>
      <style xml:id="s1" tts:fontFamily="sansSerif" tts:fontSize="100%" tts:textAlign="center"/>
    </styling>
    <layout>
      <region xml:id="bottom" tts:origin="10% 80%" tts:extent="80% 15%" tts:displayAlign="after"/>
    </layout>
  </head>
  <body region="bottom" style="s1">
    <div>
{chr(10).join(body)}
    </div>
  </body>
</tt>
'''


def decode_bytes(data: bytes) -> str:
    # Tolerant decoding for Word exports
    for enc in ("utf-8", "utf-8-sig", "windows-1252", "iso-8859-1", "macroman"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            pass
    return data.decode("utf-8", errors="replace")


# -------------------- STREAMLIT APP --------------------

st.set_page_config(page_title="TXT → TTML", layout="centered")
st.title("Convertisseur TXT → TTML (timing via speech rate)")

uploaded = st.file_uploader("Uploader un fichier .txt", type=["txt"])

split_label = st.selectbox(
    "Découpage des répliques",
    ["Par lignes vides (1 paragraphe = 1 réplique)", "Chaque ligne = 1 réplique"],
)

rate_label = st.selectbox(
    "Speech rate",
    ["WPM (mots/minute)", "CPS (caractères/seconde)"],
)

col1, col2 = st.columns(2)
with col1:
    if rate_label.startswith("WPM"):
        rate_value = st.number_input("Valeur WPM", min_value=60, max_value=300, value=160, step=5)
    else:
        rate_value = st.number_input("Valeur CPS", min_value=5.0, max_value=30.0, value=17.0, step=0.5)

with col2:
    gap = st.number_input(
        "Espace entre répliques (secondes)",
        min_value=0.2,
        max_value=5.0,
        value=1.0,
        step=0.1,
    )

lang = st.text_input("Langue (xml:lang)", value="fr")

max_dur = st.number_input("Durée max par réplique (secondes)", min_value=5.0, max_value=60.0, value=30.0, step=1.0)

if uploaded:
    raw = decode_bytes(uploaded.getvalue())

    split_mode = "blank_lines" if split_label.startswith("Par lignes vides") else "each_line"
    rate_mode = "WPM" if rate_label.startswith("WPM") else "CPS"

    raw_norm = raw.replace("\r\n", "\n").replace("\r", "\n")
    if split_mode == "each_line":
        count = sum(1 for ln in raw_norm.splitlines() if ln.strip())
    else:
        count = len([p for p in re.split(r"\n\s*\n+", raw_norm) if p.strip()])
    st.caption(f"Répliques détectées (approx) : {count}")

    if st.button("Générer TTML"):
        if rate_mode == "WPM":
            ttml = txt_to_ttml(
                raw,
                split_mode=split_mode,
                rate_mode="WPM",
                wpm=float(rate_value),
                gap=float(gap),
                lang=lang,
                max_dur=float(max_dur),
            )
        else:
            ttml = txt_to_ttml(
                raw,
                split_mode=split_mode,
                rate_mode="CPS",
                cps=float(rate_value),
                gap=float(gap),
                lang=lang,
                max_dur=float(max_dur),
            )

        st.download_button(
            "Télécharger le .ttml",
            data=ttml.encode("utf-8"),
            file_name=uploaded.name.rsplit(".", 1)[0] + ".ttml",
            mime="application/xml",
        )

        st.subheader("Aperçu")
        st.code(ttml[:4000], language="xml")