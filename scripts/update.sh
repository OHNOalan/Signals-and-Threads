#!/bin/zsh
# Signals & Threads local archive updater
#
# Usage:
#   zsh scripts/update.sh              # detect new episodes, download, rebuild episodes.json
#   zsh scripts/update.sh --meta-only  # only refresh episodes.json (no downloads)

SCRIPT_DIR="${0:A:h}"
BASE_DIR="${SCRIPT_DIR}/.."
OUT_DIR="${BASE_DIR}/transcripts"
AUDIO_DIR="${OUT_DIR}/audio"
TMP=$(mktemp -d)
trap "rm -rf $TMP" EXIT

UA='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
META_ONLY=${1:-""}

mkdir -p "$OUT_DIR" "$AUDIO_DIR" "$TMP/pages"

# ── 1. Homepage ───────────────────────────────────────────────────────────────
echo "Fetching signalsandthreads.com..."
curl -sL --max-time 30 -A "$UA" "https://signalsandthreads.com/" \
    > "$TMP/homepage.html" || true
HP=$(wc -c < "$TMP/homepage.html" | tr -d ' ')
echo "  ${HP} bytes"
[[ $HP -lt 1000 ]] && echo "ERROR: empty response — check network" && exit 1

# Quick slug count check
TOTAL=$(python3 -c "
import re, sys
d = open('$TMP/homepage.html').read()
pairs = re.findall(r'href=\"/([a-z][a-z0-9-]+)/\"[^>]*>\s*([^<\n]+?)\s*</a>', d)
seen = {}
for s,t in pairs:
    if s not in seen and t.strip(): seen[s]=1
print(len(seen))
")
echo "  $TOTAL episodes found"
[[ $TOTAL -eq 0 ]] && echo "ERROR: no episodes parsed" && exit 1

# ── 2. RSS for MP3 URLs ───────────────────────────────────────────────────────
echo "\nFetching RSS..."
curl -sL --max-time 30 -A "$UA" "https://feeds.simplecast.com/L9810DOa" \
    > "$TMP/rss.xml" || true
echo "  $(wc -c < "$TMP/rss.xml" | tr -d ' ') bytes"

# ── 3. Download new episodes ──────────────────────────────────────────────────
if [[ "$META_ONLY" != "--meta-only" ]]; then
    echo "\nChecking for new episodes..."
    NEW=0

    # get slug list inline
    python3 -c "
import re, sys
d = open('$TMP/homepage.html').read()
pairs = re.findall(r'href=\"/([a-z][a-z0-9-]+)/\"[^>]*>\s*([^<\n]+?)\s*</a>', d)
seen = {}
for s,t in pairs:
    if s not in seen and t.strip():
        seen[s]=1
        print(s)
" > "$TMP/slugs_only.txt"

    while read -r slug; do
        [[ -f "${OUT_DIR}/${slug}.html" ]] && continue
        echo "  NEW: $slug"
        NEW=$((NEW+1))

        # fetch episode page
        curl -sL --max-time 30 -A "$UA" \
            "https://signalsandthreads.com/${slug}/" \
            > "$TMP/${slug}_page.html" || true

        # find MP3 URL: try RSS first, then Simplecast API fallback
        MP3_URL=$(python3 -c "
import re, sys
try:
    rss = open('$TMP/rss.xml').read()
    import html as h
    items = re.findall(r'<item>(.*?)</item>', rss, re.DOTALL)
    for item in items:
        sm = re.search(r'signalsandthreads\.com/([a-z0-9][a-z0-9-]+)/', item)
        em = re.search(r'<enclosure[^>]+url=\"([^\"]+)\"', item)
        if sm and em and sm.group(1) == '$slug':
            print(h.unescape(em.group(1)).split('?')[0])
            break
except: pass
" 2>/dev/null || true)

        # Simplecast API fallback (handles older episodes not in RSS)
        if [[ -z "$MP3_URL" ]]; then
            EP_ID=$(python3 -c "
import re
data = open('$TMP/${slug}_page.html').read()
m = re.search(r'simplecast\.com/e/([0-9a-f-]{36})', data)
if m: print(m.group(1))
" 2>/dev/null || true)
            if [[ -n "$EP_ID" ]]; then
                MP3_URL=$(curl -s --max-time 10 "https://api.simplecast.com/episodes/$EP_ID" \
                    | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('audio_file_url',''))" 2>/dev/null || true)
                [[ -n "$MP3_URL" ]] && echo "    (MP3 via Simplecast API)"
            fi
        fi

        MP3_REL=""
        if [[ -n "$MP3_URL" ]]; then
            echo "    Downloading MP3..."
            curl -sL --max-time 120 -A "$UA" "$MP3_URL" \
                -o "${AUDIO_DIR}/${slug}.mp3" || true
            if [[ -s "${AUDIO_DIR}/${slug}.mp3" ]]; then
                echo "    Audio saved: $(du -sh "${AUDIO_DIR}/${slug}.mp3" | cut -f1)"
                MP3_REL="audio/${slug}.mp3"
            fi
        fi
        [[ -z "$MP3_REL" && -f "${AUDIO_DIR}/${slug}.mp3" ]] && MP3_REL="audio/${slug}.mp3"

        python3 "$SCRIPT_DIR/gen_html.py" \
            "$TMP/${slug}_page.html" "$slug" "$MP3_REL" "$OUT_DIR"

        sleep 0.5
    done < "$TMP/slugs_only.txt"
    echo "  $NEW new episode(s) downloaded"
fi

# ── 4. Fetch all episode pages for metadata ───────────────────────────────────
echo "\nFetching episode metadata..."
python3 -c "
import re, sys
d = open('$TMP/homepage.html').read()
pairs = re.findall(r'href=\"/([a-z][a-z0-9-]+)/\"[^>]*>\s*([^<\n]+?)\s*</a>', d)
seen = {}
for s,t in pairs:
    if s not in seen and t.strip(): seen[s]=1; print(s)
" | while read -r slug; do
    curl -sL --max-time 20 -A "$UA" \
        "https://signalsandthreads.com/${slug}/" \
        > "$TMP/pages/${slug}.html" 2>/dev/null || true
    printf "."
    sleep 0.25
done
echo " done"

# ── 5. Build episodes.json ────────────────────────────────────────────────────
echo "\nBuilding episodes.json..."
python3 "$SCRIPT_DIR/parse_episodes.py" \
    "$TMP/homepage.html" "$TMP/pages" "$OUT_DIR"

# ── 6. Rebuild index.html with inlined data (works via file://) ───────────────
echo "Rebuilding index.html..."
python3 "$SCRIPT_DIR/build_index.py" "$OUT_DIR"

echo "\nDone. Open: file://${OUT_DIR}/index.html"
echo "Tip: run 'python3 scripts/render_all.py' to regenerate all HTML from local data (no network)"
