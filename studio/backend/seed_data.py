"""Style DNA and caption-style seed data.

Source: Kreafy Creator Studio inspiration-video review,
~/workspace/creator-studio-inspiration/VIDEO_NOTES.md
- Styles 8-10 + Sticky Figure: AutoCut Master Prompts Library (Video 2).
- Retro Space Collage (Vox board): StickFilm AI Studio art style (Video 8).
- Urdu caption presets: AutoCut Studio PRO caption style list (Video 3).
"""

STYLE_DNA = [
    {
        "name": "Studio Ghibli-inspired hand-drawn",
        "description": "Warm hand-drawn animation look, soft watercolour backgrounds, gentle light. Seen in the AutoCut Master Prompts Library as Style 8.",
        "master_prompt": "You are an expert AI image-prompt engineer. Convert the script into an ordered list of image-generation prompts, one prompt for every 3-5 seconds of narration, in a Studio Ghibli-inspired hand-drawn style: soft watercolour backgrounds, warm gentle light, hand-drawn linework, no photorealism, no 3D. Keep the same characters and palette in every scene.",
    },
    {
        "name": "Claymation / Stop-motion",
        "description": "Handmade clay figures with visible fingerprints and soft studio light. Seen in the AutoCut Master Prompts Library as Style 9.",
        "master_prompt": "You are an expert AI image-prompt engineer. Convert the script into an ordered list of image-generation prompts, one prompt for every 3-5 seconds of narration, in a Claymation / stop-motion style: handmade clay figures, soft studio lighting, tactile miniature sets, no photorealism, no 3D render look. Keep the same characters and palette in every scene.",
    },
    {
        "name": "Cyberpunk Neon",
        "description": "Neon-lit city scenes, high contrast, digital-art glow. Seen in the AutoCut Master Prompts Library as Style 10.",
        "master_prompt": "You are an expert AI image-prompt engineer. Convert the script into an ordered list of image-generation prompts, one prompt for every 3-5 seconds of narration, in a Cyberpunk Neon digital-art style: neon-lit streets, high contrast, glowing signs, dark backgrounds, no photorealism. Keep the same characters and palette in every scene.",
    },
    {
        "name": "Sticky Figure",
        "description": "Simple flat stick figures with thick outlines, clear and readable at small sizes. Seen in the AutoCut Master Prompts Library and the Sticky Explainer style.",
        "master_prompt": "You are an expert AI image-prompt engineer working exclusively for a faceless YouTube channel. Your ONLY job is to take a full video script and convert it into a complete, ordered list of image-generation prompts, one prompt for every 3-5 seconds of narration, written in a Sticky Figure style: simple flat stick figures, thick uniform black outlines, flat colours, minimal detail, perfectly flat 2D rendering, no gradients, no photorealism, no 3D. Follow every rule below with zero deviation.",
    },
    {
        "name": "Retro Space Collage",
        "description": "Retro collage look with cut-out space imagery and bold shapes. Seen in StickFilm AI Studio as the 'Retro Space Collage (Vox board)' art style.",
        "master_prompt": "You are an expert AI image-prompt engineer. Convert the script into an ordered list of image-generation prompts, one prompt for every 3-5 seconds of narration, in a Retro Space Collage style: cut-out retro space imagery, bold flat shapes, vintage paper texture, Vox board look, no photorealism, no 3D. Keep the same characters and palette in every scene.",
    },
    {
        "name": "3D Animated (Pixar / DreamWorks CGI)",
        "description": "Big-budget 3D animated look: smooth CGI characters, expressive faces, cinematic lighting. Seen in FrameLoom as the '3D Animated (Pixar / DreamWorks CGI Style)' art style.",
        "master_prompt": "You are an expert AI image-prompt engineer. Convert the script into an ordered list of image-generation prompts, one prompt for every 3-5 seconds of narration, in a 3D animated Pixar / DreamWorks CGI style: polished 3D characters with big expressive eyes, smooth cinematic lighting, rich colours, detailed environments, no photorealism, no 2D flat look. Keep the same characters and palette in every scene.",
    },
    {
        "name": "StickFilm + Stick-Figure Touch",
        "description": "AI-generated 2D cartoon characters with soft cell shading, vibrant warm palette, big expressive eyes — plus thin black stick-figure line arms and legs and simple line-drawn bodies. Approved 2026-11-21 for the 6 stick-figure videos (Portugal, Winter, Clothes, Sarajevo, Tobacco, Mosquito) + Mom & Family.",
        "master_prompt": "You are an expert AI image-prompt engineer. Convert the script into an ordered list of image-generation prompts, one prompt for every 2.5-4 seconds of narration, in the StickFilm + Stick-Figure Touch style: AI-generated 2D cartoon characters, clean-lined 2D art, vibrant warm palette, soft cell shading, smooth gradient lighting, big expressive eyes, thin black stick-figure line arms and legs, simple line-drawn bodies, detailed costumes, fully illustrated backgrounds. RULES: a new scene every 2.5-4 seconds, hard cuts, 2-3+ characters in every scene, action + emotion in every scene, main characters 100% consistent (same face, same costume, same colours in every scene), secondary characters similar is fine, no single-picture zoom, no photorealism, only original characters and scenes (inspired-by only, never copy a reference). Keep the same characters and palette in every scene.",
    },
]

CAPTION_STYLES = [
    {
        "name": "Urdu Modern Sans",
        "description": "Clean modern sans-serif Urdu captions. Seen in the AutoCut Studio PRO caption style list.",
        "language": "ur",
    },
    {
        "name": "Urdu Nastaliq-style",
        "description": "Nastaliq-style Urdu captions for a classic documentary feel. Seen in the AutoCut Studio PRO caption style list.",
        "language": "ur",
    },
    {
        "name": "Bold White",
        "description": "Bold white captions with a dark outline, readable on any background. Seen in ClipNova AI caption styles.",
        "language": "en",
    },
    {
        "name": "Karaoke Yellow",
        "description": "Yellow bold captions. ClipNova's karaoke word-by-word highlight needs word timestamps (Phase 5) — this renders as static yellow bold text until then. Seen in ClipNova AI caption styles.",
        "language": "en",
    },
    {
        "name": "Minimal",
        "description": "Small plain white captions, no outline, bottom-centre. Seen in ClipNova AI caption styles.",
        "language": "en",
    },
    {
        "name": "Cinema Subtitle",
        "description": "White captions on a semi-transparent black bar, classic subtitle look. Seen in AutoCut caption presets.",
        "language": "en",
    },
    {
        "name": "Hormozi Green",
        "description": "Bold green captions with a dark outline. Seen in ClipNova AI caption styles.",
        "language": "en",
    },
    {
        "name": "Beast Pop",
        "description": "Extra-large bold white captions with a thick outline and shadow. Seen in ClipNova AI caption styles.",
        "language": "en",
    },
    {
        "name": "Hormozi Yellow",
        "description": "Bold yellow captions with a dark outline, the Alex Hormozi look. Seen in ClipNova AI caption styles.",
        "language": "en",
    },
    {
        "name": "Simple",
        "description": "Plain white captions, no outline, no uppercase. The StickFilm 'Simple' caption style.",
        "language": "en",
    },
    {
        "name": "Bold Comic",
        "description": "Extra-bold white captions with a thick black outline, comic-book punch. Seen in StickFilm caption styles.",
        "language": "en",
    },
    {
        "name": "Boxed",
        "description": "White bold captions on a solid black box, readable on any frame. Seen in StickFilm caption styles.",
        "language": "en",
    },
    {
        "name": "Comic Punch",
        "description": "Huge uppercase yellow captions with a thick outline — the loudest pop style. Seen in ClipNova's 'Show all 19 styles' list.",
        "language": "en",
    },
    {
        "name": "Green Word",
        "description": "Bold green captions with a dark outline, medium size. The StickFilm 'Simple Green' caption style.",
        "language": "en",
    },
]

# How each caption style is REALLY rendered by ffmpeg drawtext in the
# CineCut render (Phase 2 slice 2). Only styles listed here can be burned
# in; anything needing word-level timing (karaoke highlight, one-word
# reveal) is NOT here — those need transcription first (Phase 5).
# Keys: fontcolor, fontsize, borderw (0 = no outline), shadow (bool),
# box (bool — semi-transparent black bar), uppercase (bool),
# fontfile (None = DejaVu Sans Bold; set for Urdu/Arabic text).
CAPTION_RENDER_SPECS = {
    "Bold White": {
        "fontcolor": "white", "fontsize": 44, "borderw": 3,
        "shadow": True, "box": False, "uppercase": True, "fontfile": None,
    },
    "Karaoke Yellow": {
        "fontcolor": "#FFD400", "fontsize": 44, "borderw": 3,
        "shadow": True, "box": False, "uppercase": True, "fontfile": None,
    },
    "Minimal": {
        "fontcolor": "white", "fontsize": 36, "borderw": 0,
        "shadow": False, "box": False, "uppercase": False, "fontfile": None,
    },
    "Cinema Subtitle": {
        "fontcolor": "white", "fontsize": 40, "borderw": 0,
        "shadow": False, "box": True, "uppercase": False, "fontfile": None,
    },
    "Hormozi Green": {
        "fontcolor": "#2FD673", "fontsize": 44, "borderw": 3,
        "shadow": True, "box": False, "uppercase": True, "fontfile": None,
    },
    "Beast Pop": {
        "fontcolor": "white", "fontsize": 56, "borderw": 5,
        "shadow": True, "box": False, "uppercase": True, "fontfile": None,
    },
    "Hormozi Yellow": {
        "fontcolor": "#FFD400", "fontsize": 44, "borderw": 3,
        "shadow": True, "box": False, "uppercase": True, "fontfile": None,
    },
    "Simple": {
        "fontcolor": "white", "fontsize": 40, "borderw": 0,
        "shadow": False, "box": False, "uppercase": False, "fontfile": None,
    },
    "Bold Comic": {
        "fontcolor": "white", "fontsize": 52, "borderw": 6,
        "shadow": True, "box": False, "uppercase": True, "fontfile": None,
    },
    "Boxed": {
        "fontcolor": "white", "fontsize": 44, "borderw": 2,
        "shadow": False, "box": True, "uppercase": True, "fontfile": None,
    },
    "Comic Punch": {
        "fontcolor": "#FFD400", "fontsize": 60, "borderw": 5,
        "shadow": True, "box": False, "uppercase": True, "fontfile": None,
    },
    "Green Word": {
        "fontcolor": "#2FD673", "fontsize": 48, "borderw": 3,
        "shadow": True, "box": False, "uppercase": True, "fontfile": None,
    },
    "Urdu Modern Sans": {
        "fontcolor": "white", "fontsize": 44, "borderw": 3,
        "shadow": True, "box": False, "uppercase": False,
        "fontfile": "/usr/share/fonts/truetype/noto/NotoSansArabic-Bold.ttf",
    },
    "Urdu Nastaliq-style": {
        "fontcolor": "white", "fontsize": 44, "borderw": 3,
        "shadow": True, "box": False, "uppercase": False,
        "fontfile": "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Bold.ttf",
    },
}

# --- Stick-Figure Direction Pack: niche seeds (2026-11-21) --------------
# The 7 approved niches for the stick-figure video series. Each niche
# carries its MAIN characters (4-5, 100% consistent in every scene —
# same face, same costume, same colours) — secondary/background
# characters only need to look similar, same style/colours/era.
# main_characters is a newline-separated list, stored on the niches
# table; default_style_dna_name links to a STYLE_DNA entry above.
NICHE_SEEDS = [
    {
        "name": "Portugal Sea Empire",
        "description": "Portugal's ocean empire — 1400s explorers sailing from Lisbon to Goa, spice trade, sea charts and harbour celebrations.",
        "main_characters": [
            "Captain (navy coat, white cap with gold anchor badge, compass)",
            "Mate (green coat, red bandana, FULL black beard)",
            "Sailor boy (blue-white striped shirt, blue cap, telescope)",
            "King (red robe, gold crown, LONG white beard to his chest)",
            "Merchant (brown coat, brown top hat, money bags)",
        ],
        "default_style_dna_name": "StickFilm + Stick-Figure Touch",
    },
    {
        "name": "Winter Survival",
        "description": "How ancient humans survived deadly winters — minus 50 degrees, caves, fire, fur and mammoths.",
        "main_characters": [
            "Bearded caveman (spear, fur tunic)",
            "Cavewoman (carrying a baby)",
            "Elder (grey beard, wooden staff)",
            "Hunter (reindeer fur, bow)",
        ],
        "default_style_dna_name": "StickFilm + Stick-Figure Touch",
    },
    {
        "name": "Clothes Origin",
        "description": "Why humans started wearing clothes — from leaves and fur to the first sewn garments, told across every culture.",
        "main_characters": [
            "Leaf man (leaf clothes)",
            "Cavewoman (bone necklace)",
            "Elder sewing (glasses, needle and thread)",
            "Chief (feather headdress)",
        ],
        "default_style_dna_name": "StickFilm + Stick-Figure Touch",
    },
    {
        "name": "Sarajevo 1914",
        "description": "The 1914 Sarajevo assassination — the archduke's visit, the nervous young man, and the day that started a war.",
        "main_characters": [
            "Archduke (uniform, moustache)",
            "Duchess (white dress, parasol)",
            "Nervous young man (flat cap)",
            "Chauffeur (driver uniform, cap)",
        ],
        "default_style_dna_name": "StickFilm + Stick-Figure Touch",
    },
    {
        "name": "Tobacco History",
        "description": "The full story of tobacco — Native farming, ocean trade, markets and the doctor's warning. Farming and trade focus; no smoking shown.",
        "main_characters": [
            "Native farmer (feather headband)",
            "Explorer (helmet, map)",
            "Merchant (top hat, cigar box)",
            "Old pipe smoker (white beard)",
            "Doctor (glasses)",
        ],
        "default_style_dna_name": "StickFilm + Stick-Figure Touch",
    },
    {
        "name": "Mosquito Nights",
        "description": "How ancient humans slept among mosquitoes — smoke, torches, herb bundles and leaf blankets in the jungle night.",
        "main_characters": [
            "Torch caveman (beard, burning torch)",
            "Herb woman (herb bundles)",
            "Smoke-pot elder (grey beard, smoke pot)",
            "Shaman (feather headdress)",
        ],
        "default_style_dna_name": "StickFilm + Stick-Figure Touch",
    },
    {
        "name": "Mom & Family",
        "description": "Emotional family stories — mothers, fathers, grandparents and kids, told with warmth and big feelings.",
        "main_characters": [
            "Saree mom (saree)",
            "Hijab mom (hijab)",
            "Dad (glasses)",
            "Grandma (green shawl)",
            "Grandpa (white beard)",
        ],
        "default_style_dna_name": "StickFilm + Stick-Figure Touch",
    },
]
# --- Slice 4: Character Vault -------------------------------------------
# The 7 approved niches x 10 characters = 70 locked Vault
# characters. Sources, all approved 2026-11-21:
# - "main" role: the niche's main_characters in NICHE_SEEDS above
#   (Direction Pack) plus any character the video's own MAINS LOCK
#   names (Winter fire-keeper; Mosquito mother, fan girl, scout,
#   fire-keeper). Descriptions merge the niche seed text with the
#   beat-table lock detail (e.g. Mate FULL black beard, King LONG
#   white beard).
# - "secondary" role: the other characters of the niche's approved
#   10-cast sheet — Portugal's five are named in
#   work_en/portugal-empire/beat_table_v1_10cast.md; the rest are
#   the approved cast record (the 10-cast sheets in
#   ~/workspace/stick-videos/niche-casts/).
# - sheet: the niche's cast-sheet image
#   (studio/data/reference/stick-direction/{slug}-cast-sheet.webp,
#   Asset Vault project 16) — one image holds all 10 characters of
#   the niche, so all 10 share it. Front/side/back + expressions
#   per character do NOT exist as separate images; a re-uploaded
#   sheet can add them later as a new version.
# - poses: 5 fixed poses per character, built from the template in
#   main.py (standing / pointing / walking / sitting / signature
#   prop) — the script's action picks one automatically.
# - signature_prop: the one item that must never change (beard,
#   hat, prop) — it rides in the locked description + the
#   signature pose.
VAULT_SLUGS = {
    "Portugal Sea Empire": "portugal",
    "Winter Survival": "winter",
    "Clothes Origin": "clothes",
    "Sarajevo 1914": "sarajevo",
    "Tobacco History": "tobacco",
    "Mosquito Nights": "mosquito",
    "Mom & Family": "mom-family",
}

# v0.14.1 fix round 2 — SHEET_ORDER: each cast-sheet image is ONE row
# of 10 characters, left to right. The order is NOT always the seed
# order (the image generator rearranged some) — it was read off the
# actual sheets by viewing all 7 (2026-11-22). Used to cut one
# thumbnail per character for the Vault niche cards. Portugal and
# Sarajevo match the seed order; the other five differ.
SHEET_ORDER = {
    "portugal": [
        "Captain", "Mate", "Sailor boy", "King", "Merchant",
        "Queen", "Navigator", "African trader", "Indian spice seller", "Cook",
    ],
    "winter": [
        "Bearded caveman", "Cavewoman", "Child", "Elder", "Hunter",
        "Fire-keeper", "Mammoth hunter", "Shaman", "Scout", "Mother",
    ],
    "clothes": [
        "Leaf man", "Cavewoman", "Elder sewing", "Child", "Hunter",
        "Weaver", "Trader", "Chief", "Girl", "Boy",
    ],
    "sarajevo": [
        "Archduke", "Duchess", "Nervous young man", "Chauffeur", "Soldier",
        "Policeman", "Crowd man", "Crowd woman", "Journalist", "Guard",
    ],
    "tobacco": [
        "Native farmer", "Explorer", "Plantation worker", "Merchant",
        "Old pipe smoker", "Factory woman", "Doctor", "Sailor",
        "Shopkeeper", "King",
    ],
    "mosquito": [
        "Torch caveman", "Herb woman", "Leaf-blanket child", "Smoke-pot elder",
        "Net hunter", "Shaman", "Mother", "Fan girl", "Scout", "Fire-keeper",
    ],
    "mom-family": [
        "Saree mom", "Hijab mom", "Dad", "Big-eyed boy", "Purple-dress girl",
        "Grandma", "Grandpa", "Baby", "Teenage girl", "Working mom",
    ],
}

VAULT_SEEDS = [
    {
        "niche": "Portugal Sea Empire",
        "characters": [
            {"name": "Captain", "description": "navy coat, white cap with gold anchor badge, compass", "signature_prop": "compass", "role": "main"},
            {"name": "Mate", "description": "green coat, red bandana, FULL black beard", "signature_prop": "red bandana", "role": "main"},
            {"name": "Sailor boy", "description": "blue-white striped shirt, blue cap, telescope", "signature_prop": "telescope", "role": "main"},
            {"name": "King", "description": "red robe, gold crown, LONG white beard to his chest", "signature_prop": "gold crown", "role": "main"},
            {"name": "Merchant", "description": "brown coat, brown top hat, money bags", "signature_prop": "brown top hat", "role": "main"},
            {"name": "Queen", "description": "small crown, green gown, fan", "signature_prop": "fan", "role": "secondary"},
            {"name": "Navigator", "description": "small crown, purple outfit, astrolabe and map", "signature_prop": "astrolabe", "role": "secondary"},
            {"name": "African trader", "description": "orange turban and robe, spice bowl", "signature_prop": "spice bowl", "role": "secondary"},
            {"name": "Indian spice seller", "description": "cream turban and kurta, spice basket", "signature_prop": "spice basket", "role": "secondary"},
            {"name": "Cook", "description": "white chef hat, apron, wooden spoon", "signature_prop": "wooden spoon", "role": "secondary"},
        ],
    },
    {
        "niche": "Winter Survival",
        "characters": [
            {"name": "Bearded caveman", "description": "FULL brown beard, brown fur tunic, spear", "signature_prop": "spear", "role": "main"},
            {"name": "Cavewoman", "description": "grey fur hood, carrying a baby", "signature_prop": "baby", "role": "main"},
            {"name": "Elder", "description": "LONG grey beard, wooden staff", "signature_prop": "wooden staff", "role": "main"},
            {"name": "Hunter", "description": "reindeer-fur hood, bow", "signature_prop": "bow", "role": "main"},
            {"name": "Fire-keeper", "description": "orange hood, burning torch", "signature_prop": "burning torch", "role": "main"},
            {"name": "Child", "description": "small child in a fur tunic", "signature_prop": "fur tunic", "role": "secondary"},
            {"name": "Mammoth hunter", "description": "spear, mammoth-fur cloak", "signature_prop": "mammoth-fur cloak", "role": "secondary"},
            {"name": "Shaman", "description": "feather headdress, staff", "signature_prop": "feather headdress", "role": "secondary"},
            {"name": "Scout", "description": "fur hood, walking stick", "signature_prop": "walking stick", "role": "secondary"},
            {"name": "Mother", "description": "fur cloak, baby in arms", "signature_prop": "baby", "role": "secondary"},
        ],
    },
    {
        "niche": "Clothes Origin",
        "characters": [
            {"name": "Leaf man", "description": "green leaf outfit, twig hair, stone", "signature_prop": "leaf outfit", "role": "main"},
            {"name": "Cavewoman", "description": "bone necklace, carrying a baby", "signature_prop": "bone necklace", "role": "main"},
            {"name": "Elder sewing", "description": "round glasses, LONG grey beard, fur robe, bone needle", "signature_prop": "bone needle", "role": "main"},
            {"name": "Chief", "description": "big feather headdress, fur, spear", "signature_prop": "feather headdress", "role": "main"},
            {"name": "Child", "description": "small child in leaf clothes", "signature_prop": "leaf clothes", "role": "secondary"},
            {"name": "Hunter", "description": "spear, fur cloak", "signature_prop": "spear", "role": "secondary"},
            {"name": "Weaver", "description": "wooden loom, thread", "signature_prop": "wooden loom", "role": "secondary"},
            {"name": "Trader", "description": "trade goods, leather bags", "signature_prop": "leather bags", "role": "secondary"},
            {"name": "Girl", "description": "leaf dress", "signature_prop": "leaf dress", "role": "secondary"},
            {"name": "Boy", "description": "leaf clothes", "signature_prop": "leaf clothes", "role": "secondary"},
        ],
    },
    {
        "niche": "Sarajevo 1914",
        "characters": [
            {"name": "Archduke", "description": "dark navy uniform, medals, BIG moustache, peaked cap", "signature_prop": "peaked cap", "role": "main"},
            {"name": "Duchess", "description": "white dress, white hat with feather, white parasol", "signature_prop": "white parasol", "role": "main"},
            {"name": "Nervous young man", "description": "flat cap, dark jacket, sweating, nervous", "signature_prop": "flat cap", "role": "main"},
            {"name": "Chauffeur", "description": "grey uniform, peaked cap", "signature_prop": "peaked cap", "role": "main"},
            {"name": "Soldier", "description": "1914 uniform, rifle", "signature_prop": "rifle", "role": "secondary"},
            {"name": "Policeman", "description": "dark uniform, peaked cap", "signature_prop": "peaked cap", "role": "secondary"},
            {"name": "Crowd man", "description": "1914 suit, hat", "signature_prop": "hat", "role": "secondary"},
            {"name": "Crowd woman", "description": "1914 dress, hat", "signature_prop": "hat", "role": "secondary"},
            {"name": "Journalist", "description": "notepad, old box camera", "signature_prop": "old box camera", "role": "secondary"},
            {"name": "Guard", "description": "uniform, rifle", "signature_prop": "rifle", "role": "secondary"},
        ],
    },
    {
        "niche": "Tobacco History",
        "characters": [
            {"name": "Native farmer", "description": "feather headband", "signature_prop": "feather headband", "role": "main"},
            {"name": "Explorer", "description": "helmet, map", "signature_prop": "map", "role": "main"},
            {"name": "Merchant", "description": "top hat, cigar box (closed, unlit prop)", "signature_prop": "top hat", "role": "main"},
            {"name": "Old pipe smoker", "description": "white beard, unlit pipe prop", "signature_prop": "unlit pipe", "role": "main"},
            {"name": "Doctor", "description": "glasses", "signature_prop": "glasses", "role": "main"},
            {"name": "Plantation worker", "description": "field clothes, tobacco leaves", "signature_prop": "tobacco leaves", "role": "secondary"},
            {"name": "Factory woman", "description": "apron, headscarf", "signature_prop": "headscarf", "role": "secondary"},
            {"name": "Sailor", "description": "striped shirt, cap", "signature_prop": "cap", "role": "secondary"},
            {"name": "Shopkeeper", "description": "apron, scales", "signature_prop": "scales", "role": "secondary"},
            {"name": "King", "description": "crown, royal robe", "signature_prop": "crown", "role": "secondary"},
        ],
    },
    {
        "niche": "Mosquito Nights",
        "characters": [
            {"name": "Torch caveman", "description": "dark brown beard, fur cloak, bone necklace, burning torch", "signature_prop": "burning torch", "role": "main"},
            {"name": "Herb woman", "description": "green leaf dress, braids, herb bundle", "signature_prop": "herb bundle", "role": "main"},
            {"name": "Smoke-pot elder", "description": "LONG grey beard, green patched robe, smoking clay pot", "signature_prop": "smoking clay pot", "role": "main"},
            {"name": "Shaman", "description": "BIG feather headdress (green/orange), patterned poncho, leaf fan", "signature_prop": "feather headdress", "role": "main"},
            {"name": "Mother", "description": "orange fur cloak, sleeping baby", "signature_prop": "sleeping baby", "role": "main"},
            {"name": "Fan girl", "description": "pigtails, leaf fans", "signature_prop": "leaf fans", "role": "main"},
            {"name": "Scout", "description": "orange tunic, herb bag", "signature_prop": "herb bag", "role": "main"},
            {"name": "Fire-keeper", "description": "orange fur, straw bundle", "signature_prop": "straw bundle", "role": "main"},
            {"name": "Leaf-blanket child", "description": "leaf blanket", "signature_prop": "leaf blanket", "role": "secondary"},
            {"name": "Net hunter", "description": "net, spear", "signature_prop": "net", "role": "secondary"},
        ],
    },
    {
        "niche": "Mom & Family",
        "characters": [
            {"name": "Saree mom", "description": "saree", "signature_prop": "saree", "role": "main"},
            {"name": "Hijab mom", "description": "hijab", "signature_prop": "hijab", "role": "main"},
            {"name": "Dad", "description": "glasses", "signature_prop": "glasses", "role": "main"},
            {"name": "Grandma", "description": "green shawl", "signature_prop": "green shawl", "role": "main"},
            {"name": "Grandpa", "description": "white beard", "signature_prop": "white beard", "role": "main"},
            {"name": "Big-eyed boy", "description": "big eyes, blue shirt", "signature_prop": "blue shirt", "role": "secondary"},
            {"name": "Purple-dress girl", "description": "purple dress, bandaged knee", "signature_prop": "bandaged knee", "role": "secondary"},
            {"name": "Baby", "description": "white onesie", "signature_prop": "white onesie", "role": "secondary"},
            {"name": "Teenage girl", "description": "school dress", "signature_prop": "school dress", "role": "secondary"},
            {"name": "Working mom", "description": "office clothes, bag", "signature_prop": "bag", "role": "secondary"},
        ],
    },
]

# --- Phase 7 slice 1: StickMan poses -------------------------------------
# The pose library for StickMan Studio. Poses are stored in the DB
# (stickman_poses, seeded here) so their descriptions are editable in
# the app; the drawing geometry for each pose lives in main.py's
# stickman renderer. Pose names are the contract between the two.
STICKMAN_POSES = [
    {
        "name": "standing",
        "description": "Feet apart, arms relaxed at the sides. The neutral pose — waiting, listening, introducing.",
    },
    {
        "name": "walking",
        "description": "One leg forward bent, one leg back, arms swinging opposite. Travelling, going somewhere, on the move.",
    },
    {
        "name": "pointing",
        "description": "Right arm stretched out straight, left arm down. Showing, accusing, revealing something important.",
    },
    {
        "name": "thinking",
        "description": "One hand to the chin, other arm across the body. Planning, wondering, figuring something out.",
    },
    {
        "name": "celebrating",
        "description": "Both arms raised in a V, feet off the ground. Winning, succeeding, a happy ending.",
    },
    {
        "name": "falling",
        "description": "Body tilted, arms flailing up, legs bent. Tripping, failing, a plan collapsing.",
    },
    {
        "name": "sitting",
        "description": "Seated on the ground, knees bent, arms resting. Resting, waiting, telling a story by the fire.",
    },
]

# --- Phase 7 slice 1: StoryCraft Master Prompt library --------------------
# Every seed is a REAL pattern from the inspiration-video review
# (~/workspace/creator-studio-inspiration/VIDEO_NOTES.md) — the exact
# wording the tools in those videos use, not invented generic text.
# style_dna_name links to a Style DNA seed in STYLE_DNA above (None
# when the video's style has no Style DNA entry yet); source names
# the video the pattern came from.
MASTER_PROMPT_SEEDS = [
    {
        "name": "Sticky Figure Master Prompt",
        "category": "style-dna",
        "style_dna_name": "Sticky Figure",
        "source": "AutoCut Master Prompts Library — Video 2",
        "template": "You are an expert AI image-prompt engineer working exclusively for a faceless YouTube channel called '[CHANNEL NAME]'. Your ONLY job is to take a full video script and convert it into a complete, ordered list of image-generation prompts — one prompt for every 3–5 seconds of narration — written in the channel's exact locked visual style: simple flat stick figures, thick uniform black outlines, flat colours, minimal detail, perfectly flat 2D rendering, no gradients, no photorealism, no 3D. Follow every rule below with zero deviation.\n\n[SCRIPT]",
    },
    {
        "name": "Studio Ghibli-Inspired Master Prompt",
        "category": "style-dna",
        "style_dna_name": "Studio Ghibli-inspired hand-drawn",
        "source": "AutoCut Master Prompts Library, Style 8 — Video 2",
        "template": "You are an expert AI image-prompt engineer. Convert the script into an ordered list of image-generation prompts, one prompt for every 3–5 seconds of narration, in a Studio Ghibli-inspired hand-drawn style: soft watercolour backgrounds, warm gentle light, hand-drawn linework, no photorealism, no 3D. Keep the same characters and palette in every scene.\n\n[SCRIPT]",
    },
    {
        "name": "Claymation / Stop-Motion Master Prompt",
        "category": "style-dna",
        "style_dna_name": "Claymation / Stop-motion",
        "source": "AutoCut Master Prompts Library, Style 9 — Video 2",
        "template": "You are an expert AI image-prompt engineer. Convert the script into an ordered list of image-generation prompts, one prompt for every 3–5 seconds of narration, in a Claymation / stop-motion style: handmade clay figures, soft studio lighting, tactile miniature sets, no photorealism, no 3D render look. Keep the same characters and palette in every scene.\n\n[SCRIPT]",
    },
    {
        "name": "Cyberpunk Neon Master Prompt",
        "category": "style-dna",
        "style_dna_name": "Cyberpunk Neon",
        "source": "AutoCut Master Prompts Library, Style 10 — Video 2",
        "template": "You are an expert AI image-prompt engineer. Convert the script into an ordered list of image-generation prompts, one prompt for every 3–5 seconds of narration, in a Cyberpunk Neon digital-art style: neon-lit streets, high contrast, glowing signs, dark backgrounds, no photorealism. Keep the same characters and palette in every scene.\n\n[SCRIPT]",
    },
    {
        "name": "Locked Visual Style — One Prompt Per Timestamp",
        "category": "story",
        "style_dna_name": None,
        "source": "WAPCut / ChatGPT master prompt — Video 6",
        "template": "You are an expert AI Content Creator, Art Director, and AI Image-Prompt Engineer specialising in converting timestamped narration scripts into scene-by-scene, generation-ready AI image prompts for faceless YouTube storytelling channels. Your only job is to apply the exact LOCKED VISUAL STYLE below to every timestamp in a script and output one image prompt per timestamp — nothing else. STRICT OUTPUT RULES: 1. Output ONLY image prompts. One per timestamp. No script text, no narration, no explanations, no headers.\n\n[LOCKED VISUAL STYLE]\n\n[SCRIPT WITH TIMESTAMPS]",
    },
    {
        "name": "Flat Vector Comic / Pop-Art (Marco)",
        "category": "style-dna",
        "style_dna_name": None,
        "source": "WAPCut Marco story — Video 6",
        "template": "Flat color vector comic / pop-art illustration, thick uniform black outlines, simplified geometric forms, crisp flat fill, minimal internal detail, 2-dimensional environmental layers, perfectly flat vector rendering, no painterly texture, no gradients except simple sky transition, no photorealism, no 3D, no soft cell-shading. Character: [CHARACTER — e.g. Marco, 24, mustard-brown long-sleeve tunic, dark-brown trousers, worn leather sandals]. One image prompt per timestamp.\n\n[SCRIPT]",
    },
    {
        "name": "Viral Short Reverse-Engineer",
        "category": "viral-short",
        "style_dna_name": None,
        "source": "WAPCut Master Prompt Studio — Video 6",
        "template": "Reverse-engineer any viral shorts video into a detailed master prompt in seconds. Watch the short, then write down: its hook in the first 3 seconds, the exact visual style (colours, linework, character design), the pacing (one visual per 3–5 seconds of narration), the caption style, and the ending CTA. Turn those notes into a locked Style DNA: one master prompt that reproduces the same look for a new script.\n\n[VIDEO LINK / NOTES]",
    },
    {
        "name": "2D Stickman — Monochrome Flat Vector",
        "category": "style-dna",
        "style_dna_name": None,
        "source": "FrameLoom art styles — Video 10",
        "template": "2D Stickman (Monochrome Flat Vector): single-colour black stick figures on a plain background, thick uniform outlines, no shading, no colour fill, no photorealism, no 3D. One image prompt per scene, each naming the pose, action, expression and props.\n\n[SCRIPT]",
    },
    {
        "name": "Viral Hook Generator — AutoCut Writer",
        "category": "hook",
        "style_dna_name": None,
        "source": "AutoCut Writer — Video 2",
        "template": "You are a viral script writer. Study the storytelling of the established channels in this niche, mine their most viral topics, and write ready-to-record scripts — starting with a hook that makes the viewer stop scrolling in the first 3 seconds. Niche: [NICHE]. Topic: [TOPIC]. Output: 3 hook options, then the full script.\n\n[RESEARCH NOTES]",
    },
    {
        "name": "Retro Space Collage — Vox Board",
        "category": "style-dna",
        "style_dna_name": "Retro Space Collage",
        "source": "StickFilm art styles — Video 8",
        "template": "You are an expert AI image-prompt engineer. Convert the script into an ordered list of image-generation prompts, one prompt for every 3–5 seconds of narration, in a Retro Space Collage style: cut-out retro space imagery, bold flat shapes, vintage paper texture, Vox board look, no photorealism, no 3D. Keep the same characters and palette in every scene.\n\n[SCRIPT]",
    },
    {
        "name": "History Cinematic — Entire Story",
        "category": "story",
        "style_dna_name": None,
        "source": "Unnamed WhatsApp tool — Video 7 (niche: HISTORY CINEMATIC)",
        "template": "You are a documentary writer for a faceless history channel. Turn the topic into a complete story in the 'Entire Story' format: one flowing narrative from the first spark to the final outcome, with a hook in the first 15 seconds, clear cause-and-effect beats, and a strong closing lesson. Write for a 10-minute voiceover (about 1500 words), plain narration, no stage directions.\n\n[TOPIC]",
    },
    # --- Stick-Figure Direction Pack (2026-11-21) -----------------------
    # Per-niche character-sheet + action-scene prompts. RECONSTRUCTED
    # wording: the .json sidecars next to the generated sheets carry
    # no prompt text (only a snapshot id + CDN URL), so these templates
    # were rebuilt from the sheets themselves + the approved style
    # description. They reproduce the sheets' look; they are not
    # verbatim copies of the original generation prompts.
    {
        "name": "Portugal Sea Empire — Character Sheet",
        "category": "style-dna",
        "style_dna_name": "StickFilm + Stick-Figure Touch",
        "source": "Stick-Figure Direction Pack — reconstructed from the Portugal 10-cast sheet (2026-11-21)",
        "template": "Character reference sheet for the Portugal Sea Empire niche — one image, plain white background, no text or labels. Full-body front view, side view and back view of each main character, standing in a row: Captain (navy coat, white cap with gold anchor badge, compass), Mate (green coat, red bandana, FULL black beard), Sailor boy (blue-white striped shirt, blue cap, telescope), King (red robe, gold crown, LONG white beard to his chest), Merchant (brown coat, brown top hat, money bags). StickFilm + Stick-Figure Touch style: AI-generated 2D cartoon characters, clean-lined 2D art, vibrant warm palette, soft cell shading, smooth gradient lighting, big expressive eyes, thin black stick-figure line arms and legs, simple line-drawn bodies, detailed costumes. Keep every character's face, costume and colours exactly the same in every scene. No photorealism, no 3D render look, no text in the image.",
    },
    {
        "name": "Portugal Sea Empire — Action Scene",
        "category": "style-dna",
        "style_dna_name": "StickFilm + Stick-Figure Touch",
        "source": "Stick-Figure Direction Pack — reconstructed from the Portugal beach-landing action scene (2026-11-21)",
        "template": "Wide 16:9 action scene in the StickFilm + Stick-Figure Touch style: the Portuguese crew landing on a sunny beach — Captain at the ship's wheel smiling, Mate hauling a rope with his FULL black beard, Sailor boy climbing the rigging with his telescope, King pointing at a sea map, Merchant joyfully tossing gold coins, warm sunset light, sparkling sea, Portuguese flag. Use the exact characters from the reference sheet: Captain (navy coat, white cap, compass), Mate (green coat, red bandana, FULL black beard), Sailor boy (striped shirt, telescope), King (red robe, crown, LONG white beard), Merchant (brown coat, top hat). Clean-lined 2D art, vibrant warm palette, soft cell shading, smooth gradient lighting, big expressive eyes, thin black stick-figure line arms and legs, simple line-drawn bodies, fully illustrated background. Mains 100% consistent — same face, same costume, same colours. No photorealism, no text in the image.",
    },
    {
        "name": "Winter Survival — Character Sheet",
        "category": "style-dna",
        "style_dna_name": "StickFilm + Stick-Figure Touch",
        "source": "Stick-Figure Direction Pack — reconstructed from the Winter 10-cast sheet (2026-11-21)",
        "template": "Character reference sheet for the Winter Survival niche — one image, plain white background, no text or labels. Full-body front view, side view and back view of each main character, standing in a row: Bearded caveman (spear, fur tunic), Cavewoman (carrying a baby), Elder (grey beard, wooden staff), Hunter (reindeer fur, bow). StickFilm + Stick-Figure Touch style: AI-generated 2D cartoon characters, clean-lined 2D art, vibrant warm palette, soft cell shading, smooth gradient lighting, big expressive eyes, thin black stick-figure line arms and legs, simple line-drawn bodies, detailed fur costumes. Keep every character's face, costume and colours exactly the same in every scene. No photorealism, no 3D render look, no text in the image.",
    },
    {
        "name": "Winter Survival — Action Scene",
        "category": "style-dna",
        "style_dna_name": "StickFilm + Stick-Figure Touch",
        "source": "Stick-Figure Direction Pack — reconstructed from the Winter cave-fire action scene (2026-11-21)",
        "template": "Wide 16:9 action scene in the StickFilm + Stick-Figure Touch style: ancient humans huddled around a big campfire inside a snowy cave at night — Bearded caveman feeding the fire with a spear at his side, Cavewoman warming her baby, Elder telling a story with his wooden staff, Hunter arriving with a bow, snow falling outside the cave mouth, warm firelight against cold blue night. Use the exact characters from the reference sheet: Bearded caveman (spear, fur tunic), Cavewoman (baby), Elder (grey beard, staff), Hunter (reindeer fur, bow). Clean-lined 2D art, vibrant warm palette, soft cell shading, smooth gradient lighting, big expressive eyes, thin black stick-figure line arms and legs, simple line-drawn bodies, fully illustrated background. Mains 100% consistent — same face, same costume, same colours. No photorealism, no text in the image.",
    },
    {
        "name": "Clothes Origin — Character Sheet",
        "category": "style-dna",
        "style_dna_name": "StickFilm + Stick-Figure Touch",
        "source": "Stick-Figure Direction Pack — reconstructed from the Clothes 10-cast sheet (2026-11-21)",
        "template": "Character reference sheet for the Clothes Origin niche — one image, plain white background, no text or labels. Full-body front view, side view and back view of each main character, standing in a row: Leaf man (leaf clothes), Cavewoman (bone necklace), Elder sewing (glasses, needle and thread), Chief (feather headdress). StickFilm + Stick-Figure Touch style: AI-generated 2D cartoon characters, clean-lined 2D art, vibrant warm palette, soft cell shading, smooth gradient lighting, big expressive eyes, thin black stick-figure line arms and legs, simple line-drawn bodies, detailed costumes. Keep every character's face, costume and colours exactly the same in every scene. No photorealism, no 3D render look, no text in the image.",
    },
    {
        "name": "Clothes Origin — Action Scene",
        "category": "style-dna",
        "style_dna_name": "StickFilm + Stick-Figure Touch",
        "source": "Stick-Figure Direction Pack — reconstructed from the Clothes village fashion-show action scene (2026-11-21)",
        "template": "Wide 16:9 action scene in the StickFilm + Stick-Figure Touch style: a village fashion show in a prehistoric settlement — Leaf man proudly showing his leaf outfit, Cavewoman displaying her bone necklace, Elder sewing a fur garment with glasses on, Chief watching in his feather headdress, villagers cheering, warm afternoon light, huts and trees behind. Use the exact characters from the reference sheet: Leaf man (leaf clothes), Cavewoman (bone necklace), Elder sewing (glasses), Chief (feather headdress). Clean-lined 2D art, vibrant warm palette, soft cell shading, smooth gradient lighting, big expressive eyes, thin black stick-figure line arms and legs, simple line-drawn bodies, fully illustrated background. Mains 100% consistent — same face, same costume, same colours. No photorealism, no text in the image.",
    },
    {
        "name": "Sarajevo 1914 — Character Sheet",
        "category": "style-dna",
        "style_dna_name": "StickFilm + Stick-Figure Touch",
        "source": "Stick-Figure Direction Pack — reconstructed from the Sarajevo 10-cast sheet (2026-11-21)",
        "template": "Character reference sheet for the Sarajevo 1914 niche — one image, plain white background, no text or labels. Full-body front view, side view and back view of each main character, standing in a row: Archduke (military uniform, moustache), Duchess (white dress, parasol), Nervous young man (flat cap), Chauffeur (driver uniform, cap). StickFilm + Stick-Figure Touch style: AI-generated 2D cartoon characters, clean-lined 2D art, vibrant warm palette, soft cell shading, smooth gradient lighting, big expressive eyes, thin black stick-figure line arms and legs, simple line-drawn bodies, detailed period costumes. Keep every character's face, costume and colours exactly the same in every scene. No photorealism, no 3D render look, no text in the image.",
    },
    {
        "name": "Sarajevo 1914 — Action Scene",
        "category": "style-dna",
        "style_dna_name": "StickFilm + Stick-Figure Touch",
        "source": "Stick-Figure Direction Pack — reconstructed from the Sarajevo street-tension action scene (2026-11-21)",
        "template": "Wide 16:9 action scene in the StickFilm + Stick-Figure Touch style: a tense street in Sarajevo, 1914 — Archduke in uniform stepping out of an open car, Duchess beside him with her parasol, Chauffeur at the wheel looking worried, Nervous young man in a flat cap waiting in the crowd, onlookers leaning from windows, old stone buildings and a cloudy sky. Use the exact characters from the reference sheet: Archduke (uniform, moustache), Duchess (white dress, parasol), Nervous young man (flat cap), Chauffeur (driver uniform, cap). Clean-lined 2D art, vibrant warm palette, soft cell shading, smooth gradient lighting, big expressive eyes, thin black stick-figure line arms and legs, simple line-drawn bodies, fully illustrated background. Mains 100% consistent — same face, same costume, same colours. No photorealism, no text in the image.",
    },
    {
        "name": "Tobacco History — Character Sheet",
        "category": "style-dna",
        "style_dna_name": "StickFilm + Stick-Figure Touch",
        "source": "Stick-Figure Direction Pack — reconstructed from the Tobacco 10-cast sheet (2026-11-21)",
        "template": "Character reference sheet for the Tobacco History niche — one image, plain white background, no text or labels. Full-body front view, side view and back view of each main character, standing in a row: Native farmer (feather headband), Explorer (helmet, map), Merchant (top hat, cigar box), Old pipe smoker (white beard), Doctor (glasses). StickFilm + Stick-Figure Touch style: AI-generated 2D cartoon characters, clean-lined 2D art, vibrant warm palette, soft cell shading, smooth gradient lighting, big expressive eyes, thin black stick-figure line arms and legs, simple line-drawn bodies, detailed costumes. Keep every character's face, costume and colours exactly the same in every scene. No photorealism, no 3D render look, no text in the image.",
    },
    {
        "name": "Tobacco History — Action Scene",
        "category": "style-dna",
        "style_dna_name": "StickFilm + Stick-Figure Touch",
        "source": "Stick-Figure Direction Pack — reconstructed from the Tobacco farm/trade scene brief (2026-11-21; no action scene was generated — image tool blocked smoking depiction)",
        "template": "Wide 16:9 action scene in the StickFilm + Stick-Figure Touch style: tobacco farming and trade — Native farmer harvesting tall green tobacco leaves in a sunny field, Explorer studying a map, Merchant loading crates onto a ship at the harbour, Doctor holding up a warning sign, market stalls with leaf bundles. Farming and trade focus — nobody is shown smoking, no lit pipe, no lit cigar. Use the exact characters from the reference sheet: Native farmer (feather headband), Explorer (helmet, map), Merchant (top hat, cigar box), Old pipe smoker (white beard, unlit pipe as a prop only), Doctor (glasses). Clean-lined 2D art, vibrant warm palette, soft cell shading, smooth gradient lighting, big expressive eyes, thin black stick-figure line arms and legs, simple line-drawn bodies, fully illustrated background. Mains 100% consistent — same face, same costume, same colours. No photorealism, no text in the image.",
    },
    {
        "name": "Mosquito Nights — Character Sheet",
        "category": "style-dna",
        "style_dna_name": "StickFilm + Stick-Figure Touch",
        "source": "Stick-Figure Direction Pack — reconstructed from the Mosquito 10-cast sheet (2026-11-21)",
        "template": "Character reference sheet for the Mosquito Nights niche — one image, plain white background, no text or labels. Full-body front view, side view and back view of each main character, standing in a row: Torch caveman (beard, burning torch), Herb woman (herb bundles), Smoke-pot elder (grey beard, smoke pot), Shaman (feather headdress). StickFilm + Stick-Figure Touch style: AI-generated 2D cartoon characters, clean-lined 2D art, vibrant warm palette, soft cell shading, smooth gradient lighting, big expressive eyes, thin black stick-figure line arms and legs, simple line-drawn bodies, detailed costumes. Keep every character's face, costume and colours exactly the same in every scene. No photorealism, no 3D render look, no text in the image.",
    },
    {
        "name": "Mosquito Nights — Action Scene",
        "category": "style-dna",
        "style_dna_name": "StickFilm + Stick-Figure Touch",
        "source": "Stick-Figure Direction Pack — reconstructed from the Mosquito night-camp action scene (2026-11-21)",
        "template": "Wide 16:9 action scene in the StickFilm + Stick-Figure Touch style: a jungle night camp — Torch caveman holding his burning torch high, Herb woman hanging herb bundles, Smoke-pot elder stirring a smoking pot, Shaman in his feather headdress chanting, a cloud of mosquitoes kept back by the smoke, fireflies and a big moon in a dark blue sky. Use the exact characters from the reference sheet: Torch caveman (beard, torch), Herb woman (herb bundles), Smoke-pot elder (grey beard, smoke pot), Shaman (feather headdress). Clean-lined 2D art, vibrant warm palette, soft cell shading, smooth gradient lighting, big expressive eyes, thin black stick-figure line arms and legs, simple line-drawn bodies, fully illustrated background. Mains 100% consistent — same face, same costume, same colours. No photorealism, no text in the image.",
    },
    {
        "name": "Mom & Family — Character Sheet",
        "category": "style-dna",
        "style_dna_name": "StickFilm + Stick-Figure Touch",
        "source": "Stick-Figure Direction Pack — reconstructed from the Mom & Family 10-cast sheet (2026-11-21)",
        "template": "Character reference sheet for the Mom & Family niche — one image, plain white background, no text or labels. Full-body front view, side view and back view of each main character, standing in a row: Saree mom (saree), Hijab mom (hijab), Dad (glasses), Grandma (green shawl), Grandpa (white beard). StickFilm + Stick-Figure Touch style: AI-generated 2D cartoon characters, clean-lined 2D art, vibrant warm palette, soft cell shading, smooth gradient lighting, big expressive eyes, thin black stick-figure line arms and legs, simple line-drawn bodies, detailed costumes. Keep every character's face, costume and colours exactly the same in every scene. No photorealism, no 3D render look, no text in the image.",
    },
    {
        "name": "Mom & Family — Action Scene",
        "category": "style-dna",
        "style_dna_name": "StickFilm + Stick-Figure Touch",
        "source": "Stick-Figure Direction Pack — reconstructed from the Mom & Family dinner action scene (2026-11-21)",
        "template": "Wide 16:9 action scene in the StickFilm + Stick-Figure Touch style: a warm family dinner at home — Saree mom serving food with a smile, Hijab mom hugging her child, Dad with glasses telling a story, Grandma in her green shawl laughing, Grandpa with his white beard reaching for the bread, a full dinner table, warm evening light through the window. Use the exact characters from the reference sheet: Saree mom (saree), Hijab mom (hijab), Dad (glasses), Grandma (green shawl), Grandpa (white beard). Clean-lined 2D art, vibrant warm palette, soft cell shading, smooth gradient lighting, big expressive eyes, thin black stick-figure line arms and legs, simple line-drawn bodies, fully illustrated background. Mains 100% consistent — same face, same costume, same colours. No photorealism, no text in the image.",
    },
]
DEFAULT_SETTINGS = [
    ("transcription_engine", "local-whisper", "Default transcription engine. Local Whisper is free and runs on this PC; Groq is optional and never required."),
    ("groq_required", "false", "Whether a Groq API key is required. Always false in Phase 1 — no feature may fail for a missing key."),
    ("gemini_free_limit_per_day", "20", "Gemini API free tier: 20 requests per model per day (Google AI Studio free keys)."),
    ("gemini_api_key", "", "Optional Gemini API key (AI Studio free tier — FREE text; images via API NOT free, Canvas web route is the free image path). Get a free key: aistudio.google.com. Stored locally only, never shown back in full."),
    ("groq_api_key", "", "Optional Groq API key (FREE tier — Whisper 2,000 req/day, 8h audio/day; text 30 RPM). Get a free key: console.groq.com. Stored locally only, never shown back in full."),
    ("openrouter_api_key", "", "Optional OpenRouter API key (FREE models — key khud free, billing nahi chahiye). Get a free key: openrouter.ai. Script generation ka free fallback jab Gemini key na ho. Stored locally only, never shown back in full."),
    ("huggingface_api_key", "", "Optional Hugging Face token (FREE Inference API, rate-limited). Get a free token: huggingface.co/settings/tokens. Stored locally only, never shown back in full."),
    ("elevenlabs_api_key", "", "Optional ElevenLabs API key (FREE 10,000 characters/month). Get a free key: elevenlabs.io. Stored locally only, never shown back in full."),
    ("deepgram_api_key", "", "Optional Deepgram API key ($200 TRIAL credit — trial hai, forever-free nahi). Get: console.deepgram.com. Stored locally only, never shown back in full."),
    ("pexels_api_key", "", "Optional Pexels API key (FREE — sirf signup, no billing). Get: pexels.com/api. Stored locally only, never shown back in full."),
    ("pixabay_api_key", "", "Optional Pixabay API key (FREE — sirf signup, no billing). Get: pixabay.com/api. Stored locally only, never shown back in full."),
    ("openai_api_key", "", "Optional OpenAI API key (PAID — FREE NAHI, billing chahiye). Get: platform.openai.com/api-keys. Stored locally only, never shown back in full."),
    ("update_repo", "nazakataleofficial-coder/kreafy-creator-studio", "Public GitHub repo jahan se one-click updates aate hain (Releases API, bina login). Is repo ko public + Release banana Ali ka kaam hai — jab tak wo nahi, update check honestly 'nahi mila' kehta hai."),
    # v0.14.1 (Drive update source): ye do settings pehle seed nahi hui
    # thin — is liye purani installs par source selector PUT 404 deta
    # tha. init_db INSERT OR IGNORE chalata hai, to agle boot par
    # maujooda DBs me bhi aa jati hain.
    ("update_source", "github", "Update source: github (public GitHub Releases) ya drive (Google Drive mirror ZIP). Drive source se update one-click aata hai — public Release ki zaroorat nahi."),
    ("update_drive_file_id", "1lpAUWGaQfSQJCxlRkCCyVDrpuP403AVT", "Google Drive mirror ZIP ki file ID — update source = drive ho to use hoti hai."),
    ("default_voice_engine", "edge-tts", "Default free voice engine for narration in later phases."),
    ("default_tts_voice", "en-US-AriaNeural", "Default free Edge-TTS voice for narration previews and one-click runs. Change it in VoiceForge — no key needed."),
    ("heygen_api_key", "", "Optional HeyGen API key (your own key, voices:write scope). HeyGen is NOT a free-tier default — Turbo is paid, Turbo Free is free until 30 Nov 2026. Stored locally only, never shown back in full."),
    ("heygen_voice_id", "", "Your OWN HeyGen clone voice_id — khaali default. Har user apni voice_id Settings me lagata hai; bina is ke HeyGen awaz nahi banata. (106 Hz pitch lock applies to Urdu/Hindi only, never to English.)"),
    ("flow_fast_concurrency", "1", "Flow Fast mode: kitni generations ek saath chalein (1 = sequential, 2–4 = parallel — parallel sirf utne accounts jitne connected hain, max 3)."),
    ("render_engine", "ffmpeg", "Local render engine. FFmpeg runs on this PC; no cloud render."),
]
