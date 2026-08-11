from .trading_card_models import CardPackDefinition, TradingCardDefinition, TradingCardRarity

VOID_ARCHIVE_CARDS: dict[str, TradingCardDefinition] = {}


def _c(card_id: str, number: int, name: str, rarity: TradingCardRarity, description: str, art_path: str) -> TradingCardDefinition:
    card = TradingCardDefinition(
        card_id=f"void_archive_{card_id}",
        series_id="void_archive",
        number=number,
        name=name,
        rarity=rarity,
        description=description,
        art_path=f"void_archive/{rarity.value}_{art_path}.png",
    )
    VOID_ARCHIVE_CARDS[card.card_id] = card
    return card


# ── BASIC (14 cards) ──
_c("001", 1, "Lost Page", TradingCardRarity.BASIC, "A torn page from a diary that was never written.", "lost_page")
_c("002", 2, "Flicker Candle", TradingCardRarity.BASIC, "A candle that dims when you look directly at it.", "flicker_candle")
_c("003", 3, "Rusted Key", TradingCardRarity.BASIC, "It opens a lock that no longer exists.", "rusted_key")
_c("004", 4, "Dust Mote", TradingCardRarity.BASIC, "A single particle of ancient dust suspended in eternal stillness.", "dust_mote")
_c("005", 5, "Whisper Thread", TradingCardRarity.BASIC, "A strand of sound caught between two silences.", "whisper_thread")
_c("006", 6, "Forgotten Coin", TradingCardRarity.BASIC, "Currency from a kingdom erased from memory.", "forgotten_coin")
_c("007", 7, "Still Water", TradingCardRarity.BASIC, "A droplet that refuses to fall.", "still_water")
_c("008", 8, "Ash Petal", TradingCardRarity.BASIC, "A flower petal burned yet somehow still soft.", "ash_petal")
_c("009", 9, "Empty Frame", TradingCardRarity.BASIC, "A picture frame showing what was lost.", "empty_frame")
_c("010", 10, "Moth Wing", TradingCardRarity.BASIC, "Delicate wing from a moth that fed on moonlight.", "moth_wing")
_c("011", 11, "Cracked Lens", TradingCardRarity.BASIC, "Shows the world as it was, not as it is.", "cracked_lens")
_c("012", 12, "Faded Ink", TradingCardRarity.BASIC, "Ink from a quill that wrote itself dry.", "faded_ink")
_c("013", 13, "Quiet Bell", TradingCardRarity.BASIC, "A bell that rings only in dreams.", "quiet_bell")
_c("014", 14, "Bone Fragment", TradingCardRarity.BASIC, "Too small to identify, too significant to discard.", "bone_fragment")

# ── COMMON (12 cards) ──
_c("015", 15, "Archive Acolyte", TradingCardRarity.COMMON, "A junior curator who has not yet been consumed by knowledge.", "archive_acolyte")
_c("016", 16, "Shade Attendant", TradingCardRarity.COMMON, "A formless servant that organizes the stacks.", "shade_attendant")
_c("017", 17, "Scribe Wisp", TradingCardRarity.COMMON, "A floating quill that copies texts endlessly.", "scribe_wisp")
_c("018", 18, "Binding Chain", TradingCardRarity.COMMON, "Chains used to restrain particularly dangerous volumes.", "binding_chain")
_c("019", 19, "Lantern Keeper", TradingCardRarity.COMMON, "One who maintains the eternal flames of the reading halls.", "lantern_keeper")
_c("020", 20, "Memory Moth", TradingCardRarity.COMMON, "A moth that feeds on forgotten memories and glows faintly.", "memory_moth")
_c("021", 21, "Stone Gargoyle", TradingCardRarity.COMMON, "A silent sentinel guarding the outer halls.", "stone_gargoyle")
_c("022", 22, "Ink Scarab", TradingCardRarity.COMMON, "A beetle that consumes spilled ink and leaves trails of poetry.", "ink_scarab")
_c("023", 23, "Paper Wraith", TradingCardRarity.COMMON, "A spirit bound to a single crumbling manuscript.", "paper_wraith")
_c("024", 24, "Tome Spider", TradingCardRarity.COMMON, "Weaves webs between knowledge that should remain separate.", "tome_spider")
_c("025", 25, "Echo Servant", TradingCardRarity.COMMON, "Repeats the final words spoken in empty corridors.", "echo_servant")
_c("026", 26, "Dust Scholar", TradingCardRarity.COMMON, "A researcher who has been studying for centuries, now more dust than scholar.", "dust_scholar")

# ── RARE (9 cards) ──
_c("027", 27, "Void Librarian", TradingCardRarity.RARE, "Keeper of the forbidden stacks. Their eyes have seen the truth.", "void_librarian")
_c("028", 28, "Memory Thief", TradingCardRarity.RARE, "Steals memories and catalogs them like rare books.", "memory_thief")
_c("029", 29, "Clockwork Curator", TradingCardRarity.RARE, "A brass automaton that maintains the archive's impossible geometry.", "clockwork_curator")
_c("030", 30, "Rune Scribe", TradingCardRarity.RARE, "Inscribes runes that become real the moment they are read.", "rune_scribe")
_c("031", 31, "Mirror Shard", TradingCardRarity.RARE, "A fragment of a mirror that shows what you could have become.", "mirror_shard")
_c("032", 32, "Crimson Indexer", TradingCardRarity.RARE, "Catalogs books written in blood. The blood is never the author's.", "crimson_indexer")
_c("033", 33, "Gravity Well", TradingCardRarity.RARE, "A pocket of heavy silence where even light hesitates.", "gravity_well")
_c("034", 34, "Spectral Archivist", TradingCardRarity.RARE, "A ghost that remembers every book ever burned.", "spectral_archivist")
_c("035", 35, "Labyrinth Key", TradingCardRarity.RARE, "A key that shifts shape to match the lock it needs to open.", "labyrinth_key")

# ── EPIC (6 cards) ──
_c("036", 36, "Oracle of Dust", TradingCardRarity.EPIC, "Speaks prophecies formed from the decay of ancient texts.", "oracle_of_dust")
_c("037", 37, "Chained Codex", TradingCardRarity.EPIC, "A living book that must be bound at all times. It hungers.", "chained_codex")
_c("038", 38, "Null Scribe", TradingCardRarity.EPIC, "Writes words that erase themselves from existence when read.", "null_scribe")
_c("039", 39, "Void Walker", TradingCardRarity.EPIC, "One who has returned from the space between pages.", "void_walker")
_c("040", 40, "Archive Golem", TradingCardRarity.EPIC, "Constructed from compressed knowledge. It knows what you fear.", "archive_golem")
_c("041", 41, "Chronoshelves", TradingCardRarity.EPIC, "Bookshelves that contain every moment that never happened.", "chronoshelves")

# ── LEGENDARY (4 cards) ──
_c("042", 42, "Keeper of the Void", TradingCardRarity.LEGENDARY, "The silent guardian at the heart of the archive. None have heard them speak.", "keeper_of_the_void")
_c("043", 43, "The Living Archive", TradingCardRarity.LEGENDARY, "The archive itself, awakened. Every book is a thought in its mind.", "the_living_archive")
_c("044", 44, "Last Historian", TradingCardRarity.LEGENDARY, "The final witness to every ending. They record what comes after.", "last_historian")
_c("045", 45, "Soulbound Lexicon", TradingCardRarity.LEGENDARY, "A tome bound to a soul. Reading it transfers the binding.", "soulbound_lexicon")

# ── DIAMOND (3 cards) ──
_c("046", 46, "Primordial Word", TradingCardRarity.DIAMOND, "The first word ever spoken. Uttering it would unravel reality.", "primordial_word")
_c("047", 47, "Endless Tome", TradingCardRarity.DIAMOND, "A book with infinite pages. Each page you read becomes your future.", "endless_tome")
_c("048", 48, "Architect of Silence", TradingCardRarity.DIAMOND, "Designed the silence that existed before the first sound.", "architect_of_silence")

# ── PLATINUM (2 cards) ──
_c("049", 49, "The Great Nothing", TradingCardRarity.PLATINUM, "What existed before the archive. What will exist after.", "the_great_nothing")
_c("050", 50, "Void Incarnate", TradingCardRarity.PLATINUM, "The void given form. To look upon it is to understand oblivion.", "void_incarnate")


# ── Card Packs ──
VOID_ARCHIVE_PACKS: dict[str, CardPackDefinition] = {
    "void_archive_standard": CardPackDefinition(
        pack_id="void_archive_standard",
        series_id="void_archive",
        name="Void Archive Pack",
        price=350,
        cards_per_pack=3,
        description="Delve into the forgotten archives. Contains 3 cards from the Void Archive series.",
    ),
    "void_archive_premium": CardPackDefinition(
        pack_id="void_archive_premium",
        series_id="void_archive",
        name="Void Archive Premium Pack",
        price=1100,
        cards_per_pack=3,
        guaranteed_rarity=TradingCardRarity.RARE,
        description="A premium pack from the deepest stacks. Guaranteed at least one Rare or better card!",
    ),
}


def get_card(card_id: str) -> TradingCardDefinition | None:
    return VOID_ARCHIVE_CARDS.get(card_id)


def get_cards_by_rarity(rarity: TradingCardRarity) -> list[TradingCardDefinition]:
    return [c for c in VOID_ARCHIVE_CARDS.values() if c.rarity == rarity and c.released]


def get_cards_by_series(series_id: str) -> list[TradingCardDefinition]:
    return [c for c in VOID_ARCHIVE_CARDS.values() if c.series_id == series_id and c.released]


def get_all_released_cards() -> list[TradingCardDefinition]:
    return [c for c in VOID_ARCHIVE_CARDS.values() if c.released]


def get_series_total(series_id: str) -> int:
    return len(get_cards_by_series(series_id))


def get_pack(pack_id: str) -> CardPackDefinition | None:
    return VOID_ARCHIVE_PACKS.get(pack_id)


def get_all_packs() -> dict[str, CardPackDefinition]:
    return VOID_ARCHIVE_PACKS
