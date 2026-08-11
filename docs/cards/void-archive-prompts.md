# Void Archive — Card Art Generation Guide

## Rendering Notes

The bot handles the card frame, rarity badge, card name, number, and series label as overlays.
**You only need to generate the center artwork** — the illustration that lives inside the card border.

---

## Base Card Template Prompt

Generate this **once** and pass it as a reference image for every individual card prompt to maintain consistent framing and style.

```
A dark fantasy trading card template frame, 768x1024 portrait orientation. The art style should be stylized, flat-color cartoon illustration with bold clean outlines and expressive shading — similar to modern animated series like Castlevania or Hades game art. The center art area shows a subtle dark purple-to-black gradient background with stylized wispy swirls of violet and indigo smoke. The borders feature simplified silver-gray linework with a storybook illustration feel. No text, no characters, no objects — just the atmospheric backdrop. Color palette: deep purples, muted blues, charcoal black, with warm yellow-orange accent highlights. Vector-art inspired, cel-shaded, 2D animated style.
```

Save the output as `void_archive_template.png` and use it as a reference/starting image for every card below. When generating individual cards, add: `Use the attached image as the card frame and background template. Replace the blank center area with the described subject. Maintain the same stylized cartoon illustration art style.`

---

## Card Art Prompts

Each prompt assumes you're passing the template image as reference. Generate at **768x1024 PNG**.

---

### 001 — Lost Page (Basic)
**File:** `bot/assets/trading_cards/void_archive/lost_page.png`
```
Use the attached template image. In the center, a single torn page from an ancient diary floating in darkness. The page is yellowed and charred at the edges, with illegible cursive text that glows faintly silver. Tiny embers drift upward from the torn edges. The page is slightly curled, casting a soft shadow against the void background. Style matches the dark academia theme — haunting, nostalgic, high detail stylized cartoon illustration, bold outlines, cel-shaded, flat-color 2D animated style.  Card art is a simple flat-color cartoon illustration with clean bold outlines — no special visual effects. Minimal shading, clean vector-art inspired look.
```

### 002 — Flicker Candle (Basic)
**File:** `bot/assets/trading_cards/void_archive/flicker_candle.png`
```
Use the attached template image. In the center, a single tall candle standing on an invisible surface, its flame frozen in a distorted, flickering shape — as if the light itself is unsure whether to exist. The wax is obsidian black with faint silver veins. The flame casts a pale blue-white glow that barely reaches the edges. The air around the candle shows subtle heat distortion. Dark academia meets ghostly minimalism, stylized cartoon illustration, bold outlines, cel-shaded, flat-color 2D animated style.  Card art is a simple flat-color cartoon illustration with clean bold outlines — no special visual effects. Minimal shading, clean vector-art inspired look.
```

### 003 — Rusted Key (Basic)
**File:** `bot/assets/trading_cards/void_archive/rusted_key.png`
```
Use the attached template image. In the center, an ornate iron key suspended vertically in darkness. The key is heavily rusted with patches of orange-brown corrosion. The bow of the key forms a twisted geometric shape resembling a closed eye. Faint ethereal chains that are now broken dangle from the key's shaft. A single tear of liquid shadow drips from the tip. Dark fantasy, high detail. Cel-shaded cartoon illustration, bold outlines, dark fantasy style.  Card art is a simple flat-color cartoon illustration with clean bold outlines — no special visual effects. Minimal shading, clean vector-art inspired look.
```

### 004 — Dust Mote (Basic)
**File:** `bot/assets/trading_cards/void_archive/dust_mote.png`
```
Use the attached template image. In the center, a single microscopic particle of dust magnified to fill the frame, suspended in perfect stillness. The mote is crystalline and faceted, catching nonexistent light and refracting it into faint rainbows. Around it, the void is absolute except for the barest suggestion of frozen time — like the air itself has stopped moving. Ethereal macro photography style. Cel-shaded cartoon illustration, bold outlines, dark fantasy style.  Card art is a simple flat-color cartoon illustration with clean bold outlines — no special visual effects. Minimal shading, clean vector-art inspired look.
```

### 005 — Whisper Thread (Basic)
**File:** `bot/assets/trading_cards/void_archive/whisper_thread.png`
```
Use the attached template image. In the center, a single delicate silver thread extending horizontally across the dark void. The thread vibrates subtly, with tiny sound-wave distortions radiating from its center where a captured whisper is visualized as concentric ripples of pale light. The thread connects two points of complete darkness on either side. Minimalist, ethereal, high detail. Cel-shaded cartoon illustration.  Card art is a simple flat-color cartoon illustration with clean bold outlines — no special visual effects. Minimal shading, clean vector-art inspired look.
```

### 006 — Forgotten Coin (Basic)
**File:** `bot/assets/trading_cards/void_archive/forgotten_coin.png`
```
Use the attached template image. In the center, an ancient coin floating in darkness. The coin is tarnished copper-green with a face engraved on one visible side — but the face has been deliberately scratched and gouged, rendered unrecognizable. Faint wisps of violet mist rise from the coin's surface as if the memory attached to it is evaporating. The edge of the coin shows symbols belonging to no known alphabet. Dark fantasy. Cel-shaded cartoon illustration, bold outlines, dark fantasy style.  Card art is a simple flat-color cartoon illustration with clean bold outlines — no special visual effects. Minimal shading, clean vector-art inspired look.
```

### 007 — Still Water (Basic)
**File:** `bot/assets/trading_cards/void_archive/still_water.png`
```
Use the attached template image. In the center, a single perfect droplet of water suspended mid-air, refusing to fall. The droplet is crystal clear, acting as a tiny lens that shows a distorted reflection of a library of infinite bookshelves within it. The surface tension is visibly perfect — not a single ripple. Below the droplet, the void waits patiently. Macro surrealism, stylized cartoon illustration, bold outlines, cel-shaded, flat-color 2D animated style.  Card art is a simple flat-color cartoon illustration with clean bold outlines — no special visual effects. Minimal shading, clean vector-art inspired look.
```

### 008 — Ash Petal (Basic)
**File:** `bot/assets/trading_cards/void_archive/ash_petal.png`
```
Use the attached template image. In the center, a single flower petal made entirely of ash, floating in darkness. The petal somehow maintains the delicate veining and soft curve of a living rose petal, but it is charcoal gray and crumbling at the very edge. A single ember glows within the ash, pulsing like a heartbeat. The petal leaves a faint trail of drifting ash particles as if it recently fell from a burned garden. Haunting beauty. Cel-shaded cartoon illustration, bold outlines, dark fantasy style.  Card art is a simple flat-color cartoon illustration with clean bold outlines — no special visual effects. Minimal shading, clean vector-art inspired look.
```

### 009 — Empty Frame (Basic)
**File:** `bot/assets/trading_cards/void_archive/empty_frame.png`
```
Use the attached template image. In the center, an ornate empty picture frame floating in darkness, angled slightly. The frame is gilded silver, intricately carved with vines and thorns, but heavily tarnished. Where a picture should be, there is only more void — but slightly lighter than the surrounding darkness, revealing the ghostly silhouette of what was once there: the outline of two figures standing together, now erased. Melancholic dark academia. Cel-shaded cartoon illustration, bold outlines, dark fantasy style.  Card art is a simple flat-color cartoon illustration with clean bold outlines — no special visual effects. Minimal shading, clean vector-art inspired look.
```

### 010 — Moth Wing (Basic)
**File:** `bot/assets/trading_cards/void_archive/moth_wing.png`
```
Use the attached template image. In the center, a single detached moth wing floating in darkness. The wing is translucent with an iridescent sheen that shifts between silver and pale blue. The delicate scales are visible in microscopic detail, and faint motes of moonlight-colored dust fall from the torn edge where it was separated from the body. The wing pattern forms an eye-like marking that seems to follow the viewer. Macro dark fantasy. Cel-shaded cartoon illustration, bold outlines, dark fantasy style.  Card art is a simple flat-color cartoon illustration with clean bold outlines — no special visual effects. Minimal shading, clean vector-art inspired look.
```

### 011 — Cracked Lens (Basic)
**File:** `bot/assets/trading_cards/void_archive/cracked_lens.png`
```
Use the attached template image. In the center, a circular glass lens floating in darkness, cracked down the middle. Through one half, the world appears normal — a glimpse of an ordinary reading room. Through the cracked half, the same room is shown in ruins, centuries decayed, with ghostly figures still seated at their desks. The crack itself emits a faint blue-white light. Surreal dark fantasy. Cel-shaded cartoon illustration, bold outlines, dark fantasy style.  Card art is a simple flat-color cartoon illustration with clean bold outlines — no special visual effects. Minimal shading, clean vector-art inspired look.
```

### 012 — Faded Ink (Basic)
**File:** `bot/assets/trading_cards/void_archive/faded_ink.png`
```
Use the attached template image. In the center, a glass inkwell floating in darkness, tipped on its side. A single drop of midnight-blue ink hangs from the rim, frozen mid-fall. The ink glows with an inner light. Spilled ink on an invisible surface below has formed into words that are already fading — the last sentence is still legible: "I was here." The quill that wrote them has turned to dust beside the inkwell. Dark academia. Cel-shaded cartoon illustration, bold outlines, dark fantasy style.  Card art is a simple flat-color cartoon illustration with clean bold outlines — no special visual effects. Minimal shading, clean vector-art inspired look.
```

### 013 — Quiet Bell (Basic)
**File:** `bot/assets/trading_cards/void_archive/quiet_bell.png`
```
Use the attached template image. In the center, a small silver handbell floating in darkness. The bell is intricately engraved with constellations that no longer exist. The clapper hangs motionless. Around the bell, faint sound-wave ripples are frozen in mid-propagation — the bell rang once, long ago, and the sound never finished traveling. Pale blue light emanates from within the bell's dome. Ethereal minimalism. Cel-shaded cartoon illustration, bold outlines, dark fantasy style.  Card art is a simple flat-color cartoon illustration with clean bold outlines — no special visual effects. Minimal shading, clean vector-art inspired look.
```

### 014 — Bone Fragment (Basic)
**File:** `bot/assets/trading_cards/void_archive/bone_fragment.png`
```
Use the attached template image. In the center, a small bone fragment floating in darkness, illuminated by an unseen light source from below. The bone is ancient and yellowed, too small to identify — perhaps a finger bone, perhaps something else entirely. Faint carved runes are visible on its surface, pulsing with a dim violet light. The fragment casts a long shadow that does not match any light source in the scene. Dark fantasy archaeology. Cel-shaded cartoon illustration, bold outlines, dark fantasy style.  Card art is a simple flat-color cartoon illustration with clean bold outlines — no special visual effects. Minimal shading, clean vector-art inspired look.
```

### 015 — Archive Acolyte (Common)
**File:** `bot/assets/trading_cards/void_archive/archive_acolyte.png`
```
Use the attached template image. A hooded young acolyte in dark gray robes kneels in the center of the frame, holding a single candle that illuminates their face from below. Their eyes are wide with both wonder and fear. Behind them, the faint suggestion of impossibly tall bookshelves receding into darkness. The acolyte's shadow stretches behind them but splits into three separate shadows. Dark academia character art, soft chiaroscuro lighting, stylized cartoon illustration, bold outlines, cel-shaded, flat-color 2D animated style.  The subject has a subtle soft edge glow in its corresponding accent color, adding gentle depth. Slightly more detailed shading than basic cards, but still flat-color cel-shaded style.
```

### 016 — Shade Attendant (Common)
**File:** `bot/assets/trading_cards/void_archive/shade_attendant.png`
```
Use the attached template image. In the center, a formless translucent figure made of shifting gray smoke, vaguely humanoid in shape. The shade attendant is shown organizing floating books with extended tendrils of shadow-stuff, placing a leather-bound tome onto an invisible shelf. Its face is a smooth void with two pinpricks of pale light where eyes would be. Dark fantasy spectral being. Cel-shaded cartoon illustration, bold outlines, dark fantasy style.  The subject has a subtle soft edge glow in its corresponding accent color, adding gentle depth. Slightly more detailed shading than basic cards, but still flat-color cel-shaded style.
```

### 017 — Scribe Wisp (Common)
**File:** `bot/assets/trading_cards/void_archive/scribe_wisp.png`
```
Use the attached template image. In the center, a floating ball of pale golden light with a quill pen orbiting around it like a moon. The wisp emits a warm glow that pushes back the surrounding darkness. It hovers over an invisible desk, and ghostly letters are writing themselves onto empty air — an endless stream of text flowing from the quill's tip. The letters glow briefly before fading. Dark academia meets fantasy spirit. Cel-shaded cartoon illustration, bold outlines, dark fantasy style.  The subject has a subtle soft edge glow in its corresponding accent color, adding gentle depth. Slightly more detailed shading than basic cards, but still flat-color cel-shaded style.
```

### 018 — Binding Chain (Common)
**File:** `bot/assets/trading_cards/void_archive/binding_chain.png`
```
Use the attached template image. In the center, a heavy iron chain coiled in darkness, each link engraved with tiny warding runes that glow with suppressed crimson light. The chain is wrapped around something unseen — a shape in the darkness that the chain barely contains. One link has cracked, and from the crack, a tendril of absolute black is seeping out. The chain is taut, straining against whatever it holds. Dark fantasy, high detail. Cel-shaded cartoon illustration, bold outlines, dark fantasy style.  The subject has a subtle soft edge glow in its corresponding accent color, adding gentle depth. Slightly more detailed shading than basic cards, but still flat-color cel-shaded style.
```

### 019 — Lantern Keeper (Common)
**File:** `bot/assets/trading_cards/void_archive/lantern_keeper.png`
```
Use the attached template image. In the center, a cloaked figure in deep brown robes walks through darkness carrying a massive iron lantern on a pole. The lantern contains not fire but a captured star — a miniature sun that pulses with warm orange-gold light. The keeper's face is shadowed beneath their hood, but their hands are visible: weathered, ancient, covered in small burn scars. Around them, the darkness physically recoils from the lantern's light. Dark fantasy. Cel-shaded cartoon illustration, bold outlines, dark fantasy style.  The subject has a subtle soft edge glow in its corresponding accent color, adding gentle depth. Slightly more detailed shading than basic cards, but still flat-color cel-shaded style.
```

### 020 — Memory Moth (Common)
**File:** `bot/assets/trading_cards/void_archive/memory_moth.png`
```
Use the attached template image. In the center, a large moth with wings patterned like pages from an old book — complete with visible text and illustrations on its wings. The moth glows faintly with a soft blue luminescence. Tiny motes of light trail behind it like forgotten thoughts. Its antennae are shaped like quill pens. The moth hovers above an open palm made of shadow reaching up from below. Surreal dark fantasy creature. Cel-shaded cartoon illustration, bold outlines, dark fantasy style.  The subject has a subtle soft edge glow in its corresponding accent color, adding gentle depth. Slightly more detailed shading than basic cards, but still flat-color cel-shaded style.
```

### 021 — Stone Gargoyle (Common)
**File:** `bot/assets/trading_cards/void_archive/stone_gargoyle.png`
```
Use the attached template image. In the center, a crouching stone gargoyle perched on an ornate pedestal. The gargoyle's body is weathered gray stone with moss and cracks running through it. Its mouth is open in a silent snarl, and its carved eyes seem to follow the viewer. One clawed hand grips the pedestal's edge. Behind it, the faint outline of massive stone pillars suggests the entrance to the archive. Dark fantasy architecture guardian. Cel-shaded cartoon illustration, bold outlines, dark fantasy style.  The subject has a subtle soft edge glow in its corresponding accent color, adding gentle depth. Slightly more detailed shading than basic cards, but still flat-color cel-shaded style.
```

### 022 — Ink Scarab (Common)
**File:** `bot/assets/trading_cards/void_archive/ink_scarab.png`
```
Use the attached template image. In the center, a large beetle with a carapace made of polished obsidian, crawling across an invisible surface. The scarab leaves a trail of glowing blue ink behind it — the trail forms itself into flowing cursive poetry that shimmers briefly before sinking into the darkness. The beetle's mandibles are stained with ink. Its eyes are tiny faceted gems that reflect a library that doesn't exist in the scene. Dark fantasy insect macro. Cel-shaded cartoon illustration, bold outlines, dark fantasy style.  The subject has a subtle soft edge glow in its corresponding accent color, adding gentle depth. Slightly more detailed shading than basic cards, but still flat-color cel-shaded style.
```

### 023 — Paper Wraith (Common)
**File:** `bot/assets/trading_cards/void_archive/paper_wraith.png`
```
Use the attached template image. In the center, a ghostly figure whose body is made entirely of torn manuscript pages, loosely bound together in a humanoid shape. The pages overlap like feathers, covered in dense handwritten text. The wraith's face is a single blank page where words occasionally appear and vanish. One outstretched hand dissolves into individual pages that float away into the darkness. Dark academia spectral being. Cel-shaded cartoon illustration, bold outlines, dark fantasy style.  The subject has a subtle soft edge glow in its corresponding accent color, adding gentle depth. Slightly more detailed shading than basic cards, but still flat-color cel-shaded style.
```

### 024 — Tome Spider (Common)
**File:** `bot/assets/trading_cards/void_archive/tome_spider.png`
```
Use the attached template image. In the center, a spider with a body made of a miniature leather-bound book — the book's spine forms its abdomen, pages fan out as legs. Its eight legs are made of black ink that drips and reforms with each step. The book-body occasionally flips open to reveal pages covered in webs of text that connect to the spider's legs. It hangs from a single silk thread descending from the darkness above. Dark fantasy creature. Cel-shaded cartoon illustration, bold outlines, dark fantasy style.  The subject has a subtle soft edge glow in its corresponding accent color, adding gentle depth. Slightly more detailed shading than basic cards, but still flat-color cel-shaded style.
```

### 025 — Echo Servant (Common)
**File:** `bot/assets/trading_cards/void_archive/echo_servant.png`
```
Use the attached template image. In the center, a translucent humanoid figure composed of concentric sound-wave rings, like a shockwave frozen in human shape. The servant's mouth is open in an eternal repetition of someone else's final words, visualized as rippling text circles emanating outward. Its hands are cupped around its mouth as if calling into a vast empty hall. The figure is pale blue-white and semi-transparent. Ethereal dark fantasy. Cel-shaded cartoon illustration, bold outlines, dark fantasy style.  The subject has a subtle soft edge glow in its corresponding accent color, adding gentle depth. Slightly more detailed shading than basic cards, but still flat-color cel-shaded style.
```

### 026 — Dust Scholar (Common)
**File:** `bot/assets/trading_cards/void_archive/dust_scholar.png`
```
Use the attached template image. In the center, a seated figure hunched over a desk, reading a book by candlelight. The figure is mostly human but partially dissolved into drifting dust particles — their lower body and one arm have already become particles floating away. The dust swirls in lazy patterns that suggest it might reform. The book they read glows with importance. The candle has burned down to almost nothing. Dark academia, melancholic. Cel-shaded cartoon illustration, bold outlines, dark fantasy style.  The subject has a subtle soft edge glow in its corresponding accent color, adding gentle depth. Slightly more detailed shading than basic cards, but still flat-color cel-shaded style.
```

### 027 — Void Librarian (Rare)
**File:** `bot/assets/trading_cards/void_archive/void_librarian.png`
```
Use the attached template image. In the center, a tall robed figure in deep purple-black vestments stands before an impossible wall of books. The librarian's face is obscured by a smooth silver mask with no features except two narrow eye slits that glow with cold blue light. One hand holds an open tome that emits its own dark radiance. The other hand is raised, fingers curled as if commanding silence. Behind them, books float off their shelves and orbit in lazy circles. Dark fantasy authority figure, high detail stylized cartoon illustration, bold outlines, cel-shaded, flat-color 2D animated style.  Small scattered holographic shimmer particles float around and across the subject — tiny iridescent sparkles of silver-blue light that catch the eye. The card art feels more dimensional with subtle multi-layer shading while maintaining the cel-shaded cartoony style.
```

### 028 — Memory Thief (Rare)
**File:** `bot/assets/trading_cards/void_archive/memory_thief.png`
```
Use the attached template image. In the center, a lithe figure in dark leather and silk, hooded and masked, reaching into a floating orb of light with long, elegant fingers. The orb contains a captured memory — visible as a tiny diorama of a happy family dinner, frozen in time. The thief is extracting the memory, pulling it out as a glowing silver thread. Around them, more captured memory orbs are strung like lanterns on invisible chains. Dark fantasy rogue. Cel-shaded cartoon illustration, bold outlines, dark fantasy style.  Small scattered holographic shimmer particles float around and across the subject — tiny iridescent sparkles of silver-blue light that catch the eye. The card art feels more dimensional with subtle multi-layer shading while maintaining the cel-shaded cartoony style.
```

### 029 — Clockwork Curator (Rare)
**File:** `bot/assets/trading_cards/void_archive/clockwork_curator.png`
```
Use the attached template image. In the center, a humanoid automaton made of brass and copper, with exposed gears ticking in its chest cavity. The curator holds a massive ring of keys at its belt and an open pocket watch in one mechanical hand. Its face is a polished brass plate with etched features and lenses for eyes that glow amber. Behind it, impossible staircases and shifting hallways of the archive are faintly visible, bending at wrong angles. Steampunk dark fantasy. Cel-shaded cartoon illustration, bold outlines, dark fantasy style.  Small scattered holographic shimmer particles float around and across the subject — tiny iridescent sparkles of silver-blue light that catch the eye. The card art feels more dimensional with subtle multi-layer shading while maintaining the cel-shaded cartoony style.
```

### 030 — Rune Scribe (Rare)
**File:** `bot/assets/trading_cards/void_archive/rune_scribe.png`
```
Use the attached template image. In the center, a robed figure kneels on the ground, using a crystalline stylus to carve glowing runes into a stone tablet. Each completed rune detaches from the stone and floats into the air, becoming a three-dimensional sigil of light. The scribe's arms are covered in the same runes, permanently etched into their skin. Their face shows intense concentration. The runes in the air begin to form a larger pattern — a spell being assembled. Dark fantasy magic user. Cel-shaded cartoon illustration, bold outlines, dark fantasy style.  Small scattered holographic shimmer particles float around and across the subject — tiny iridescent sparkles of silver-blue light that catch the eye. The card art feels more dimensional with subtle multi-layer shading while maintaining the cel-shaded cartoony style.
```

### 031 — Mirror Shard (Rare)
**File:** `bot/assets/trading_cards/void_archive/mirror_shard.png`
```
Use the attached template image. In the center, a jagged shard of mirror glass floating in darkness, large enough to reflect a full figure. The reflection shows not the viewer but an alternate version — the same person but in royal attire, or in rags, depending on choices never made. The mirror's edge is bleeding liquid silver that drips upward, defying gravity. Cracks in the glass show different possible lives in each fragment. Surreal dark fantasy. Cel-shaded cartoon illustration, bold outlines, dark fantasy style.  Small scattered holographic shimmer particles float around and across the subject — tiny iridescent sparkles of silver-blue light that catch the eye. The card art feels more dimensional with subtle multi-layer shading while maintaining the cel-shaded cartoony style.
```

### 032 — Crimson Indexer (Rare)
**File:** `bot/assets/trading_cards/void_archive/crimson_indexer.png`
```
Use the attached template image. In the center, a pale figure in white robes stained with crimson handprints, seated at a writing desk. The indexer dips a quill into an inkwell that contains blood rather than ink, and writes in a massive ledger. The names written in the ledger glow red. Dozens of identical ledgers float in stacks around the indexer. Their eyes are entirely red with no pupils. The quill writes without the indexer looking at the page. Dark fantasy horror. Cel-shaded cartoon illustration, bold outlines, dark fantasy style.  Small scattered holographic shimmer particles float around and across the subject — tiny iridescent sparkles of silver-blue light that catch the eye. The card art feels more dimensional with subtle multi-layer shading while maintaining the cel-shaded cartoony style.
```

### 033 — Gravity Well (Rare)
**File:** `bot/assets/trading_cards/void_archive/gravity_well.png`
```
Use the attached template image. In the center, a sphere of condensed darkness that warps the space around it. Light bends and stretches as it approaches, creating a lensing effect that distorts the background. Books and loose pages orbit the well in degrading spirals, some already torn apart by the gravitational forces. The well itself is perfectly black — a hole in reality. At its event horizon, faint purple light bleeds through cracks in spacetime. Cosmic dark fantasy. Cel-shaded cartoon illustration, bold outlines, dark fantasy style.  Small scattered holographic shimmer particles float around and across the subject — tiny iridescent sparkles of silver-blue light that catch the eye. The card art feels more dimensional with subtle multi-layer shading while maintaining the cel-shaded cartoony style.
```

### 034 — Spectral Archivist (Rare)
**File:** `bot/assets/trading_cards/void_archive/spectral_archivist.png`
```
Use the attached template image. In the center, a translucent ghost floating cross-legged above the ground, surrounded by floating scrolls and books that orbit in a gentle spiral. The archivist's spectral form flickers like a flame, sometimes solid, sometimes barely visible. Ghostly hands extend from its form to adjust and catalog the floating texts. Its face is sad and knowing — it died in this archive and chose to stay. Ethereal dark fantasy. Cel-shaded cartoon illustration, bold outlines, dark fantasy style.  Small scattered holographic shimmer particles float around and across the subject — tiny iridescent sparkles of silver-blue light that catch the eye. The card art feels more dimensional with subtle multi-layer shading while maintaining the cel-shaded cartoony style.
```

### 035 — Labyrinth Key (Rare)
**File:** `bot/assets/trading_cards/void_archive/labyrinth_key.png`
```
Use the attached template image. In the center, a key made of shifting, liquid metal that constantly reforms into different shapes — now an ornate skeleton key, now a geometric prism, now a spiral. The key floats in darkness with faint blue energy crackling along its surface. Around it, ghostly afterimages of all its previous forms hang in the air like echoes. The key casts a shadow that does not match any of its current shapes. Surreal dark fantasy artifact. Cel-shaded cartoon illustration, bold outlines, dark fantasy style.  Small scattered holographic shimmer particles float around and across the subject — tiny iridescent sparkles of silver-blue light that catch the eye. The card art feels more dimensional with subtle multi-layer shading while maintaining the cel-shaded cartoony style.
```

### 036 — Oracle of Dust (Epic)
**File:** `bot/assets/trading_cards/void_archive/oracle_of_dust.png`
```
Use the attached template image. In the center, an ancient figure wrapped in tattered gray robes, seated in a throne made of compacted books. The oracle's eyes are completely white — blind, but seeing everything. Dust continuously falls from their robes like sand in an hourglass, pooling at their feet. The dust forms prophecies on the ground — words written in the particles that rearrange themselves. One hand is raised with fingers spread, dust streaming between them. Behind them, a massive stained glass window shows a scene that hasn't happened yet. Epic dark fantasy. Cel-shaded cartoon illustration, bold outlines, dark fantasy style.  Pronounced holographic foil effect across the entire card art. Visible starburst sparkles and radiant light flares emanate from the focal point of the subject. A luminous purple-magenta energy aura surrounds the central figure or object. Stronger depth and richer multi-tone shading, still within the stylized cartoon illustration aesthetic.
```

### 037 — Chained Codex (Epic)
**File:** `bot/assets/trading_cards/void_archive/chained_codex.png`
```
Use the attached template image. In the center, a massive living book bound in what appears to be skin, floating upright. Heavy iron chains wrap around the codex from all directions, anchored to invisible points in the darkness. The book strains against its chains, pages flipping violently on their own. A single eye opens on the cover — large, reptilian, golden. Teeth have grown along the book's edges. Wisps of dark energy leak from between the pages. Dark fantasy horror artifact. Cel-shaded cartoon illustration, bold outlines, dark fantasy style.  Pronounced holographic foil effect across the entire card art. Visible starburst sparkles and radiant light flares emanate from the focal point of the subject. A luminous purple-magenta energy aura surrounds the central figure or object. Stronger depth and richer multi-tone shading, still within the stylized cartoon illustration aesthetic.
```

### 038 — Null Scribe (Epic)
**File:** `bot/assets/trading_cards/void_archive/null_scribe.png`
```
Use the attached template image. In the center, a figure made of negative space — a humanoid cutout in reality, through which absolute nothingness is visible. The null scribe writes with a pen that leaves trails of erasure, deleting the darkness and leaving behind blinding white. The words they write vanish from existence the moment they are read by anyone, leaving a sense of having forgotten something important. The figure's edges shimmer with white static. Surreal cosmic horror. Cel-shaded cartoon illustration, bold outlines, dark fantasy style.  Pronounced holographic foil effect across the entire card art. Visible starburst sparkles and radiant light flares emanate from the focal point of the subject. A luminous purple-magenta energy aura surrounds the central figure or object. Stronger depth and richer multi-tone shading, still within the stylized cartoon illustration aesthetic.
```

### 039 — Void Walker (Epic)
**File:** `bot/assets/trading_cards/void_archive/void_walker.png`
```
Use the attached template image. In the center, a figure stepping through a tear in reality — one foot still in the darkness of the void, one foot entering the archive. The walker wears a long coat made of starlight that shifts and pulses. Their face is calm, but their eyes hold the reflection of things no living being should witness. Behind them, the tear shows a view of absolute nothing — no stars, no light, no concept of space. They carry a lantern that contains the last light from a dead universe. Epic cosmic fantasy. Cel-shaded cartoon illustration, bold outlines, dark fantasy style.  Pronounced holographic foil effect across the entire card art. Visible starburst sparkles and radiant light flares emanate from the focal point of the subject. A luminous purple-magenta energy aura surrounds the central figure or object. Stronger depth and richer multi-tone shading, still within the stylized cartoon illustration aesthetic.
```

### 040 — Archive Golem (Epic)
**File:** `bot/assets/trading_cards/void_archive/archive_golem.png`
```
Use the attached template image. In the center, a massive humanoid construct built from thousands of compressed books, pages, scrolls, and manuscripts, all fused together into a towering form. Runic glowing lines trace across its body like veins of knowledge. Its head is a massive open tome with two glowing spheres for eyes. It stands guard in a grand hallway, one fist planted on the ground. Knowledge literally leaks from cracks in its body as streams of golden light. Epic dark fantasy construct. Cel-shaded cartoon illustration, bold outlines, dark fantasy style.  Pronounced holographic foil effect across the entire card art. Visible starburst sparkles and radiant light flares emanate from the focal point of the subject. A luminous purple-magenta energy aura surrounds the central figure or object. Stronger depth and richer multi-tone shading, still within the stylized cartoon illustration aesthetic.
```

### 041 — Chronoshelves (Epic)
**File:** `bot/assets/trading_cards/void_archive/chronoshelves.png`
```
Use the attached template image. In the center, a section of bookshelves that extend infinitely in all directions, but each shelf shows a different moment in time — one holds books from the past, still pristine; another shows books from a future that may never happen, half-formed and translucent. Clock faces are embedded into the shelf framework, all showing different times. Ghostly hands reach between shelves, retrieving books from one timeline and placing them into another. The shelves bend in impossible M.C. Escher geometry. Epic surreal dark fantasy. Cel-shaded cartoon illustration, bold outlines, dark fantasy style.  Pronounced holographic foil effect across the entire card art. Visible starburst sparkles and radiant light flares emanate from the focal point of the subject. A luminous purple-magenta energy aura surrounds the central figure or object. Stronger depth and richer multi-tone shading, still within the stylized cartoon illustration aesthetic.
```

### 042 — Keeper of the Void (Legendary)
**File:** `bot/assets/trading_cards/void_archive/keeper_of_the_void.png`
```
Use the attached template image. In the center, a lone figure seated on a throne of crystallized darkness at the heart of the archive. The keeper wears armor forged from compressed silence — plates of absolute black that absorb all light. Their helmet is featureless except for a single vertical line of pale silver light where eyes should be. One hand rests on an impossibly large key, the other holds an open book from which constellations drift upward. Around them, the void itself seems to breathe. The keeper has waited here since before there was anything to keep. Legendary dark fantasy, stylized cartoon masterpiece.  Full shimmering holofoil appearance like a rare Pokemon card. Constellation patterns of golden light trace across the background, and the subject emanates a radiant energy field of warm orange-gold. Dynamic action-like composition with dramatic rim lighting. Star-burst highlights and light rays burst from behind the subject. Bold colors, rich shadows, cel-shaded style with visible holofoil sparkle texture overlay.
```

### 043 — The Living Archive (Legendary)
**File:** `bot/assets/trading_cards/void_archive/the_living_archive.png`
```
Use the attached template image. In the center, the archive itself personified as a colossal, semi-abstract face formed from bookshelves, staircases, reading rooms, and endless corridors all woven together into a vaguely human visage. Each bookshelf is a wrinkle, each window an eye, each floating lantern a thought. Knowledge literally circulates through the being like blood — glowing streams of text and diagrams flowing between sections. The expression is ancient, patient, omniscient. Legendary conceptual dark fantasy, stylized cartoon epic scale.  Full shimmering holofoil appearance like a rare Pokemon card. Constellation patterns of golden light trace across the background, and the subject emanates a radiant energy field of warm orange-gold. Dynamic action-like composition with dramatic rim lighting. Star-burst highlights and light rays burst from behind the subject. Bold colors, rich shadows, cel-shaded style with visible holofoil sparkle texture overlay.
```

### 044 — Last Historian (Legendary)
**File:** `bot/assets/trading_cards/void_archive/last_historian.png`
```
Use the attached template image. In the center, an impossibly old figure seated at a writing desk that extends into infinity. The historian has been recording endings since the first thing ended. Their quill is made from a phoenix feather that still smolders. The book they write in is simultaneously blank and full — every ending they record frees up space for more. Behind them, a window shows the final sunset of a world they watched die. Their face shows both infinite sorrow and infinite peace. Legendary dark academia, stylized cartoon masterpiece.  Full shimmering holofoil appearance like a rare Pokemon card. Constellation patterns of golden light trace across the background, and the subject emanates a radiant energy field of warm orange-gold. Dynamic action-like composition with dramatic rim lighting. Star-burst highlights and light rays burst from behind the subject. Bold colors, rich shadows, cel-shaded style with visible holofoil sparkle texture overlay.
```

### 045 — Soulbound Lexicon (Legendary)
**File:** `bot/assets/trading_cards/void_archive/soulbound_lexicon.png`
```
Use the attached template image. In the center, a massive tome bound in what appears to be living, breathing material. A spectral chain connects the book's spine to a floating human soul — a translucent blue-white form of a person, their chest tethered to the lexicon. The soul's eyes are closed in peaceful acceptance. The book's pages glow with the memories and knowledge of every previous owner, their faces flickering across the pages like afterimages. The chain pulses with shared life force. Legendary dark fantasy artifact. Cel-shaded cartoon illustration, bold outlines, dark fantasy style.  Full shimmering holofoil appearance like a rare Pokemon card. Constellation patterns of golden light trace across the background, and the subject emanates a radiant energy field of warm orange-gold. Dynamic action-like composition with dramatic rim lighting. Star-burst highlights and light rays burst from behind the subject. Bold colors, rich shadows, cel-shaded style with visible holofoil sparkle texture overlay.
```

### 046 — Primordial Word (Diamond)
**File:** `bot/assets/trading_cards/void_archive/primordial_word.png`
```
Use the attached template image. At the absolute center, a single floating word written in a language that predates language itself — a symbol of pure crystalline light that hurts to look at directly. The word is in the process of being spoken, visualized as sound waves of creation emanating outward, each wave birthing smaller concepts, words, and ideas that cascade into the darkness. Reality itself seems to bend around the word. The background shows the moment before the first sound — absolute, pregnant silence. Diamond-tier cosmic fantasy, stylized cartoon masterpiece.  Crystalline geometric holofoil effect — the artwork appears as if viewed through a faceted diamond prism. Refracted rainbow light beams split across the image with sharp geometric angles. The subject is rendered with an icy cyan-blue luminescence and a shimmering diamond-dust particle field. The cel-shaded cartoon lines are outlined in bright cyan-white, creating a glowing neon-edge effect. Prismatic light fractals frame the composition. Premium collector look.
```

### 047 — Endless Tome (Diamond)
**File:** `bot/assets/trading_cards/void_archive/endless_tome.png`
```
Use the attached template image. In the center, an open book floating in darkness, its pages extending infinitely in both directions — the book has no beginning and no end. The visible spread shows a scene being written in real-time: a tiny figure walking through the pages, and the text they walk through becomes their future path. The book's pages glow with golden light along the edges. Vines made of ink script wrap around the book's binding. Reading one page causes the next to be written. Diamond-tier surreal fantasy. Cel-shaded cartoon illustration, bold outlines, dark fantasy style.  Crystalline geometric holofoil effect — the artwork appears as if viewed through a faceted diamond prism. Refracted rainbow light beams split across the image with sharp geometric angles. The subject is rendered with an icy cyan-blue luminescence and a shimmering diamond-dust particle field. The cel-shaded cartoon lines are outlined in bright cyan-white, creating a glowing neon-edge effect. Prismatic light fractals frame the composition. Premium collector look.
```

### 048 — Architect of Silence (Diamond)
**File:** `bot/assets/trading_cards/void_archive/architect_of_silence.png`
```
Use the attached template image. In the center, a figure made of geometric crystalline forms, faceted like a diamond sculpture, standing in a pose of creation. The architect holds a pair of celestial compasses, drawing the blueprint of silence itself — visible as a mandala of sound-negating patterns. Where the compass touches, reality goes mute. The figure has no face, only a smooth crystalline surface that reflects the viewer's own contemplation. Behind them, completed sections of silence are visible as spheres of perfect stillness. Diamond-tier conceptual fantasy, stylized cartoon masterpiece.  Crystalline geometric holofoil effect — the artwork appears as if viewed through a faceted diamond prism. Refracted rainbow light beams split across the image with sharp geometric angles. The subject is rendered with an icy cyan-blue luminescence and a shimmering diamond-dust particle field. The cel-shaded cartoon lines are outlined in bright cyan-white, creating a glowing neon-edge effect. Prismatic light fractals frame the composition. Premium collector look.
```

### 049 — The Great Nothing (Platinum)
**File:** `bot/assets/trading_cards/void_archive/the_great_nothing.png`
```
Use the attached template image. The image should depict the concept of absolute nothing — but somehow visible. A vast expanse of what appears to be empty space, but upon closer inspection, it is not black but a shimmering white-gold void that contains the potential of everything that does not yet exist. At the exact center, a single point of light — the moment before the first something. Faint translucent shapes of things that might one day be created drift at the edges like afterimages of a dream not yet dreamed. This is what was here before the archive. This is what will be here after. Platinum-tier cosmic philosophical fantasy, stylized cartoon masterpiece with subtle platinum-white metallic highlights throughout.  Full-spectrum rainbow holographic foil with a liquid platinum metallic sheen flowing across the artwork. The entire image shimmers with iridescent refraction like a Pokemon secret rare or Yu-Gi-Oh ghost rare. A brilliant white-gold ethereal corona frames the subject. Light cascades and bends across the surface in sweeping arcs. The cel-shaded cartoon illustration has been elevated with an overlaid platinum foil texture and subtle rainbow chromatic aberration at the edges. This is the ultimate chase card — visually unmistakable from every other rarity.
```

### 050 — Void Incarnate (Platinum)
**File:** `bot/assets/trading_cards/void_archive/void_incarnate.png`
```
Use the attached template image. In the center, the void given physical form — a humanoid figure whose body is the event horizon of a black hole, perfectly dark, yet surrounded by a corona of platinum-white light that reveals its silhouette. The figure's outline is clear, but inside it is absolute absence — looking at its face is looking at oblivion. One hand extends forward, palm up, offering either annihilation or enlightenment — the viewer cannot tell which. Stars, galaxies, and entire timelines fall into the figure's form like water into a drain, compressed into rings of light around it. The expression, despite having no features, conveys both terror and an incomprehensible peace. Platinum-tier cosmic horror masterpiece, stylized cartoon illustration, bold outlines, with subtle platinum sparkle effects in the corona.

To gaze upon this card is to understand oblivion itself.  Full-spectrum rainbow holographic foil with a liquid platinum metallic sheen flowing across the artwork. The entire image shimmers with iridescent refraction like a Pokemon secret rare or Yu-Gi-Oh ghost rare. A brilliant white-gold ethereal corona frames the subject. Light cascades and bends across the surface in sweeping arcs. The cel-shaded cartoon illustration has been elevated with an overlaid platinum foil texture and subtle rainbow chromatic aberration at the edges. This is the ultimate chase card — visually unmistakable from every other rarity.
```

---

## Usage Workflow

1. Generate the **Base Card Template** using the prompt above. Save as `void_archive_template.png`.
2. For each card, pass the template image as reference and use the individual prompt.
3. Each generated image should be **768x1024 PNG**.
4. Save to `bot/assets/trading_cards/void_archive/` with the exact filename from the `**File:**` line.
5. The bot's render service will overlay the card frame, rarity badge, name, and series label automatically.