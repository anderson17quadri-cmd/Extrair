---
name: image-carousel
description: Fetch images from the web (or from local files) and assemble them into a professional-looking, editorial-style numbered carousel — the standard multi-image post format for Instagram, LinkedIn, and similar platforms. Also writes the slide-by-slide script itself from just a topic (no need to supply slide text) — use this whenever the user asks to "criar um carrossel sobre X", "montar um carrossel de imagens", make an Instagram/LinkedIn carousel, turn a set of pictures/URLs into a slide sequence, or wants several images resized to the same aspect ratio for a social post — even with nothing more than a topic and no ready-made text, and even if they just say "pega umas imagens da net e monta um carrossel" without listing exact URLs. Always aim for the "what good looks like" bar below (tag pills, condensed impact typography, cinematic gradients, a consistent footer) — a plain white-bold-text-on-solid-color slide reads as amateur and should not be the default.
---

# Image Carousel

Build a ready-to-upload image carousel with real editorial design, not just resized photos with text slapped on. Output is a numbered sequence of JPEGs in upload order.

## What good looks like (read this before building anything)

This skill's visual language was reverse-engineered from real, well-performing Instagram carousels (news pages, sports pages, business/dashboard accounts). The pattern that separates "looks professional" from "looks like a template" is almost always the same handful of moves — use them by default, every time, not just when explicitly asked for something "criativo":

1. **A small colored tag/pill above the headline** — a category, a moment, a one-line hook ("GOL DA VITÓRIA", "#1 GEOPOLÍTICA", "MOMENTO VIRAL"). This single element does more work than anything else to make a slide feel curated instead of generic. Every slide with a headline should have one.
2. **A cinematic gradient scrim behind text, never a flat translucent box.** Real carousels darken a gradient region of the photo itself (transparent → ~90% black at the edge). A rounded semi-transparent rectangle around the text reads as an amateur PowerPoint. `apply_gradient_scrim()` in the script does this — use it, don't reintroduce a boxed panel.
3. **Condensed, bold display type for headlines**, a separate clean font for body/subtitle text. Plain system-bold centered text is the #1 giveaway of a low-effort slide. The bundled fonts (`assets/fonts/`) are `BigShoulders-Bold.ttf` for headlines (this is very close to what the reference "Alerta Global"-style news carousels use) and `Outfit-Bold.ttf` for body/subtitles.
4. **Two-tone headlines**: split the headline across a neutral color (white) and an accent color for the word(s) that matter most — this is the `title=`/`accent=` split in the `text:` spec. Reference carousels almost always color-break their headline this way ("REINO UNIDO TEM NOVO" white / "PRIMEIRO-MINISTRO" red).
5. **A consistent footer/watermark** repeated on every slide in the set (`--footer`) — but keep it to identity, not disclaimer. A handle, a brand name, a short source credit on a news carousel: yes. A generic legal-sounding line like "informação geral, não substitui aconselhamento médico" on a fun listicle: no — it reads as boilerplate and drags the whole set down. If the topic doesn't need a citation (recipes, trends, curiosities, opinion) and there's no handle to brand it with, it's fine to skip `--footer` entirely rather than invent filler text for the slot.
6. **Every single slide carries a real image — no exceptions by default.** Cover and closing slides are not an excuse for a flat color card: find a real photo, map, chart, or diagram related to the topic and use it as the background (`text:bg=<url-or-path>|tag=..|title=..`). A flat/banded color background (`--bg-color`, `--band-colors`) is a last-resort fallback for when no relevant image exists at all — it is not the default, and a set where the cover/closing are flat color while the middle slides have photos looks inconsistent and unfinished. Spend the extra search before settling for solid color.
7. **Always cite sources — but in the caption, never on the image.** Any slide presenting facts, stats, or claims — and definitely any news/current-events carousel — needs a source credit. That credit goes in the Instagram caption's source line (§4), not in `--footer` or anywhere on the slide itself: `--footer` is reserved for identity (handle/brand), not citations. For fast-moving topics, include the as-of date in that caption source line so the content doesn't read as evergreen when it isn't (e.g. `"Fontes: CNN, Al Jazeera · até DD/MM/AAAA"`).

If a request is explicitly for something minimal/plain, it's fine to simplify — but the default, unprompted output should already look like the above, not need a "make it prettier" follow-up.

## 0. Roteiro do carrossel (write the script before touching images)

When the user gives only a topic — no ready-made slide text ("cria um carrossel sobre X", "faz um carrossel de 5 erros ao marcar corte de cabelo online") — write the full script yourself, directly, in the same turn. Don't ask the user to supply copy; that defeats the point of this step.

- **Sempre em português europeu**: "utilizador" not "usuário", "ecrã" not "tela", "ficheiro" not "arquivo", "ratinho" not "mouse", contracted forms avoided in headline copy either way. This applies to every generated word — tags, titles, subtitles, footer, CTA — regardless of what language the rest of the conversation with the user is happening in.
- **Slide 1 (hook)**: one sentence, scroll-stopping. Contrarian claim, a number promise ("5 erros que..."), a direct challenge, or a bold statement — not a bland topic label.
- **Slides intermédios**: um ponto/uma ideia por slide, frase curta (**máx. 15-20 palavras**). If a point needs more than that to land, it's two slides, not one dense slide — this is the same "3-4 segundos por slide" constraint that drives the whole visual system in this skill.
- **Curiosidade em vez de informação seca**: a subtitle line that just states a fact flatly ("Contém vitamina C") is a missed opportunity — reach for the angle that makes someone stop scrolling ("Tem mais vitamina C do que a laranja"). Same fact, but framed as a surprise/comparison/stake instead of a textbook sentence. This applies to every slide's subtitle, not just the hook.
- **Every factual claim gets verified against a directly-fetched primary source before it goes on a slide — no exceptions, and this is not optional for "curiosidades"/trend content just because it feels low-stakes.** `WebSearch`'s own summary is a lead, not a source: this skill shipped a carousel with a fabricated statistic and two invented trend claims because the search tool's synthesized answer was trusted at face value instead of checked. What actually happened, concretely: a claim about "banana caramelizada" being a 2026 trend turned out to not appear in *either* of the two articles the search summary cited it from — it only became verifiable after directly fetching a *third* article that genuinely listed it. A "pistache é o sabor mais quente de 2026" claim was directly contradicted by the source once fetched (it said the opposite: pistachio is *past* peak hype). A "matcha e yuzu" claim never appeared in any of five directly-fetched articles at all — it had been invented somewhere in the search summarization and had to be dropped and replaced with a verified flavor (paçoca) instead. The rule this forces: after `WebSearch` surfaces candidate sources, `WebFetch` (or `curl`) the actual article(s) and confirm the specific claim, number, quote, or name is really there before writing it into a slide. If a claim can't be found stated directly in a fetched source, don't use it — find a different, verifiable claim rather than keeping the interesting-sounding one.
- **Check roughly 5 independent sources before treating a trend/statistical/"everyone says" claim as established — not just the first one that confirms it.** A single article repeating a claim doesn't mean it's true (blogs and news sites copy each other constantly); it takes checking multiple independent sources to tell a real trend from one site's invented or exaggerated framing. This is also how a false claim actually gets caught in practice — the "matcha e yuzu" claim above wasn't disproven by one contradicting source, it was disproven by checking five sources and finding it in *none* of them. In practice: for anything presented as a trend, ranking, or "X is the top/hottest/most popular Y," pull up several distinct outlets/reports (not five search results that all cite the same original article — check they're actually independent) before stating it as fact. If sources disagree or only one obscure source makes the claim, either drop it, hedge it explicitly ("segundo [fonte específica]..."), or say only what the corroborated sources actually support.
- **Slide count**: 6-8 by default. Only ask the user first if the *tone* is genuinely ambiguous (educativo / vendas / storytelling) — don't ask about slide count, don't ask them to write copy, don't ask permission to proceed.
- **Último slide** depends on what's actually behind the carousel — don't apply the growth-content ending by rote:
  | Situation | Closing slide |
  |---|---|
  | Content for/about a specific person or account (their tips, their brand, their story) | Clear CTA — "segue", "guarda", "comenta", "link na bio". Pairs naturally with the `type=cta` slide and `--profile-*` flags from §2.1. |
  | Informational / news / no personal account behind it (explainers, recaps, current-events) | A sober closing fact or summary line instead — no "segue-me". Forcing a follow-CTA onto reporting undercuts it; see the auto-detection table in §2.1. |

The finished script is what drives everything downstream: each slide's line(s) become the `tag=`/`title=`/`accent=`/`subtitle=`/`number=` fields (§2) and steer what to search for as the background image (§1) — the script comes first, image sourcing serves it, not the other way round.

## 1. Get the source images

- **User gave URLs or local files directly** → use them as-is, in the order given.
- **User described a topic instead of giving URLs** → use `WebSearch` to find images. Prioritize **current, on-topic, real photos** over generic/older stock photos — if the carousel is about a specific event, search for photos *from that event* (e.g. `site:commons.wikimedia.org <player> <event date>`, or pull `og:image` from news articles about the specific event — see the curl technique below). Don't default to a person's random old headshot when a current, on-topic photo exists.
- **Licensing**: prefer Wikimedia Commons (`https://commons.wikimedia.org/wiki/Special:FilePath/<File name>.jpg` redirects straight to the image) for anything that might get reused or posted commercially — it's unambiguously free to use. If the user explicitly authorizes pulling from anywhere (news sites, etc.), that's fine for personal/informational use, but say so plainly: agency/press photos carry copyright risk for commercial or paid-promotion use, even if fine for a casual repost.
- **Extracting a photo URL from a news article**: `WebFetch` on a news URL often won't surface the real image (dynamic loading, or the AI summary drops it). Instead:
  ```bash
  curl -sSL -A "Mozilla/5.0" "<article-url>" | grep -oE '<meta property="og:image"[^>]*>'
  ```
  This reliably gets the article's hero image even when the page itself is JS-heavy.
- **Always look at the photo before using it** (read it, don't just trust a filename) — check the crop will keep the subject in frame at the target aspect ratio, and check no unrelated/awkward third party dominates the frame (this actually happened: a "Messi" slide accidentally centered on a politician standing next to him — always eyeball it).
- **Never reuse the same photo twice in one carousel — every slide gets its own distinct image, full stop.** This includes the "bookend" pattern (same photo on the cover and the closing slide) — it might look like a deliberate callback, but the user just told us plainly they don't want a repeated photo, and a set where two slides share an image reads as "ran out of material," not as an intentional device. If a topic only has one strong photo available, that's a sign to search harder for a second angle/subject/moment — not to reuse the one you already have.
- **The photo must show the specific thing the slide's text is talking about — not just the same category.** This bit the skill for real: a slide whose text described a specific viral dessert ("X-Bolo", a hamburger-shaped cake with a specific filling) got illustrated with a generic photo of a *different, unrelated* dessert (a plain flan) that merely shared a keyword — technically "on-topic" in category, wrong in substance. Same trap with "banana caramelizada" — a whipped-cream tart with no banana in frame is not a match just because a recipe article used that headline. Before accepting a photo, ask: if the caption says X, does the image actually, visibly show X (the specific product/dish/person/moment), not just something adjacent to it? If a first search only turns up generic/adjacent photos, keep searching with more specific terms (the exact product name, "receita [prato] foto", the specific event date) rather than settling — see the pistachio/banana/pudim example in this skill's own build history: the fix was searching recipe-blog `og:image`s for the literal named dish until the photo actually matched, not accepting the nearest generic stock shot.
- Ask for the number of slides if unspecified; a typical carousel is 5-10 images. Instagram accepts up to 10, LinkedIn up to 20.

## 2. Build the carousel

```bash
python3 scripts/build_carousel.py \
  "<url-or-path-1>" "<url-or-path-2>" "text:tag=..|title=..|accent=..|subtitle=.." \
  --output-dir <destination-folder> \
  --ratio 4:5 \
  --accent-color "#FFC800" \
  --footer "@handle · one-line credit"
```

Each source is one of:
- an **image URL or local path** — center-cropped to the target ratio and resized.
- **`text:tag=..|title=..|accent=..|subtitle=..|bg=<url-or-path>`** — a generated cover/closing card. Only `title` is required. `accent` is a second headline line rendered in the accent color (the two-tone headline effect). **Always pass `bg=` with a real, on-topic photo/map/chart** — it's composited full-bleed behind the gradient scrim and text, same as a photo caption slide, just with a stronger darken pass since real images are busier than flat color. Only omit `bg=` (falling back to `--bg-color`/`--band-colors`) when no relevant image exists at all for that slide.

Key options:
- `--ratio` — `4:5` (default, standard Instagram/LinkedIn portrait), `1:1`, `16:9`, or `9:16`.
- `--width` — output width in pixels (default 1080).
- `--accent-color` — hex color used for tag pills, accent headline words, and subtitle text. Pick something that fits the subject (team colors, brand colors) — check it has contrast against whatever it'll sit on (see gotcha below).
- `--band-colors "#c1,#c2,#c3"` — paints the background of `text:` cards as three horizontal stripes (1:2:1 ratio) instead of a flat `--bg-color`, e.g. for a national flag: Spain `"#AA151B,#F1BF00,#AA151B"`. A uniform darkening pass is applied automatically under any band background so text stays legible everywhere, regardless of accent color.
- `--footer "text"` — small identity line (handle/brand) repeated on every slide. Strongly recommended (see point 5 above). Not for source citations — those go in the caption (point 7 above, §4).
- `--captions-file` — JSON list, same length as sources, of `null` or `{"tag": "..", "title": "..", "subtitle": ".."}` to caption photo slides (person name-tag over a gradient scrim, with the same tag-pill treatment as cover cards).
- `--no-badge` — drop the small "N/total" slide-count chip (top-right, subtle by design — it should never compete with the tag pill).

**Gotcha**: don't pick an accent color that matches one of your `--band-colors` (e.g. gold accent text on a gold flag stripe is invisible even with the darkening pass helping) — check headline/accent copy will actually be legible against every band before finalizing.

**Gotcha**: the bundled fonts don't have emoji glyphs — an emoji character in any text field renders as a broken tofu box (`▢`), not the emoji. Don't put emoji in `title=`/`tag=`/`subtitle=`/captions; write the word instead ("compartilhe" not "🔥").

**Handled automatically, no workaround needed**: `story` slide `body=` text with `**highlight**` spans followed immediately by punctuation (e.g. `**highlighted phrase**, more text`) used to render a stray gap before the punctuation — `parse_highlight_spans` now glues punctuation directly touching a `**` boundary onto the adjacent word, so just write natural punctuation and don't worry about where exactly the `**` closes relative to a comma/period. Similarly, `fetch_image` now retries with backoff (up to 3 attempts) when a host returns a 200 with a non-image body (e.g. Wikimedia's "robot policy" page after several fast requests) — if you still see repeated download failures from the same host, slow down the request rate yourself rather than hammering retries.

## 2.1 Optional add-ons (v2.0 — all opt-in, off unless requested)

These layer on top of everything above without changing how images are sourced. Use them when they fit the content — don't bolt a "follow me" CTA onto a neutral news explainer, and don't force a personal-brand header onto a one-off topical carousel.

**Profile header** (photo-or-initials circle + name/handle, top-left, every slide) — for carousels that represent a person/account's own content:
```bash
--profile-name "Ana Ferreira" --profile-handle "@anaferreira.cria" [--profile-photo path/to/photo.jpg]
```
No photo → falls back to an initials circle in the accent color automatically. Once a profile is set, it also appears on the CTA slide's bottom-right and drives the initials/photo there.

**Persistent profile config** — save `{"name", "handle", "photo", "accent_color", "footer"}` to a JSON file once per account and pass `--profile-config path.json` on every future carousel instead of retyping `--profile-name`/`--accent-color`/`--footer` each time. Explicit CLI flags always override the config file if both are given. Ask the user once whether they want this saved (e.g. next to their carousel outputs) if they're clearly building a recurring series for the same account.

**Progress-bar indicator** — an alternative to the default "N/total" corner chip, closer to native Instagram carousel dots:
```bash
--indicator-style bar
```
Automatically adapts track/fill/label colors for light vs. dark slides (e.g. the CTA slide).

**Big number** (`number=` field, in a `text:` spec or a `captions-file` entry) — for numbered-list content (tips, mistakes, steps) where a tag pill undersells the structure. Draws a large accent-colored digit before the tag/title:
```
"text:number=1|title=TEXTO DEMAIS|accent=NUM SLIDE SÓ|subtitle=..."
```
Use this instead of (or alongside) the tag pill when the content is explicitly "N things" — auto-detect this from the request itself ("5 erros", "3 dicas", "os 4 motivos") rather than asking.

**CTA/closing slide** (`text:type=cta|title=..|accent=..|question=..|cta=..|prompt=..`) — a deliberately light background (`--cta-bg`, default warm off-white) regardless of the rest of the carousel's palette: the pattern-break signals "this is the ask." Fields: `title`/`accent` (short two-line headline), `question` (engagement prompt), `cta` (a casual follow-up line), `prompt` (defaults to "Compartilhe, salve e siga"). **Only use this when there's a real account/profile behind the carousel** — an informational or news carousel (sports recap, current-events explainer) should not end with a "follow me" slide; end those with a plain `text:` closing card instead.

**Style auto-detection principle** (borrowed from a reference skill, adapted to this system rather than importing its 4 separate visual styles): let the content's shape pick the treatment, applied *within* the tag/gradient/typography system above, not as a competing aesthetic —
| Content shape | Treatment |
|---|---|
| Numbered tips/mistakes/steps | `number=` big digit per slide |
| Person/moment/story | tag pill + name (the default `add_name_caption` behavior) |
| Stat/data point | `text:` card, no image needed if genuinely no photo exists, otherwise `bg=` a real chart/graph |
| Personal-brand content with a following | profile header + CTA closing slide |
| News/informational, no personal account behind it | no profile header, no CTA slide — close on a plain `text:` card instead |

## 3. Hand off

Render at least 2-3 slides inline (cover + one photo slide) so the user can sanity-check crop, color contrast, and text placement before treating the set as final — don't just report file paths. If any source failed to download, the script reports it on stderr and continues with the rest — surface those failures rather than silently shipping a shorter carousel than requested.

**Final delivery, always, no exceptions:**
- **Zip the finished set** (`zip -j out.zip out_dir/*.jpg`) and send that, not just the loose files — this is the deliverable, every time, not something to ask about first.
- **Render at a high output width** — `--width 1920` (giving 1920x2400 at 4:5) rather than the 1080 default, unless the user asks for something smaller or a specific platform spec. 1080 is Instagram's minimum native width, not a quality target.
- **Prefer higher-resolution source photos when there's a choice.** A news site's `og:image` is usually capped around 1200px wide regardless of the original photo's real size — that's fine when it's the only option, but if a higher-res original exists (the AFP/Reuters wire version, a Wikimedia Commons upload, the publication's in-article image rather than its social-share crop), use that instead. Upscaling a 1200px photo to a 1920px canvas is a visible quality compromise, not a neutral one — it's worth the extra search when it's avoidable.

## 4. Instagram caption (always, every carousel)

Every time a carousel is delivered, also write and deliver a ready-to-post Instagram caption for it — not just the slide images. This is a standing rule, not something to be asked for per request.

- Written in the same voice/language as the roteiro (§0 — European Portuguese by default).
- Structure: a hook line (can echo or riff on the cover headline, doesn't have to repeat it verbatim), 2-4 short lines of body text expanding or teasing the content, then a call-to-engagement line, then a source line (if the carousel presents facts/stats/claims — see rule 7 above: `"Fontes: CNN, Al Jazeera · até DD/MM/AAAA"`), then hashtags.
- Hashtags: 5-15, relevant to the topic and niche — not generic spam tags (`#instagood #photooftheday`). Mix broad + specific (e.g. for a cake carousel: `#bolo #confeitaria #docesbrasileiros` + specific flavor tags).
- Deliver the caption as plain text in the reply, clearly separated from everything else — the user copy-pastes it straight into Instagram, so don't wrap it in extra commentary or bury it mid-paragraph. A short fenced block or a clearly-labeled "Legenda:" section works.
