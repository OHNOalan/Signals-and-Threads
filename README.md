# Signals & Threads — Local Archive

Offline archive of the [Jane Street engineering podcast](https://signalsandthreads.com/).  
28 episodes · full transcripts · MP3 audio · Chinese bilingual translations

```bash
open transcripts/index.html   # no server needed
```

---

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

---

## Commands

| Task | Command |
|---|---|
| Check for new episodes, download, rebuild index | `zsh scripts/update.sh` |
| Metadata only (no downloads) | `zsh scripts/update.sh --meta-only` |
| Translate all untranslated episodes | `.venv/bin/python scripts/translate_google.py` |
| Fill in failed/missing paragraphs only | `.venv/bin/python scripts/translate_google.py --fix-gaps` |
| Translation status | `.venv/bin/python scripts/translate_google.py --list` |
| Translate one episode | `.venv/bin/python scripts/translate_google.py <slug>` |
| Rebuild all HTML (bakes translations inline) | `.venv/bin/python scripts/render_all.py` |

---

## Typical workflow after a new episode drops

```bash
zsh scripts/update.sh
.venv/bin/python scripts/translate_google.py
.venv/bin/python scripts/render_all.py
```
