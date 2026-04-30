from __future__ import annotations  # Allow postponed evaluation of type annotations until runtime

import re  # Provide regular expression helpers for parsing Tenhou packet lines

from dataclasses import dataclass, field  # Import dataclass utilities for lightweight data containers
from enum import Enum, IntEnum  # Import Enum types for integer and string based enumerations
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple  # Bring in typing helpers for collection annotations


class Player(IntEnum):  # Enumerate the four seating positions in a Tenhou game
    """Enumeration for the four seats used in Tenhou logs."""  # Class docstring explaining seat enumeration

    JICHA = 0  # East seat represented by integer 0
    SHIMOCHA = 1  # South seat represented by integer 1
    TOIMEN = 2  # West seat represented by integer 2
    KAMICHA = 3  # North seat represented by integer 3

    @classmethod  # Decorator indicating the following method is a class method
    def from_code(cls, code: str) -> "Player":  # Convert a single-letter seat code into the corresponding Player value
        """Convert a one-letter seat code found in packets into a Player."""  # Docstring documenting conversion logic
        mapping = {  # Mapping from packet codes to Player members
            "T": cls.JICHA,  # Code T corresponds to the self seat
            "U": cls.SHIMOCHA,  # Code U denotes the player to the right
            "V": cls.TOIMEN,  # Code V denotes the opposite player
            "W": cls.KAMICHA,  # Code W denotes the player to the left
        }  # Close mapping dictionary literal
        try:  # Attempt to look up the provided code in the mapping
            return mapping[code]  # Return the Player value associated with the code
        except KeyError as exc:  # Handle unknown codes that are not present in the mapping
            raise ValueError(f"Unknown player code: {code}") from exc  # Raise a clearer error with context

    @classmethod  # Use a class method so callers can convert numeric indices into Player members
    def from_index(cls, index: Optional[int]) -> Optional["Player"]:  # Convert an optional numeric index into Player
        """Convert a numeric player index (0-3) into the Player enum, returning None when absent."""  # Explain optional behaviour
        if index is None:  # Short-circuit when no index was provided
            return None  # Propagate absence
        try:  # Attempt to wrap the integer in the enum
            return cls(index)  # Return the matching Player member
        except ValueError as exc:  # Guard against malformed indices
            raise ValueError(f"Unknown player index: {index}") from exc  # Provide context for debugging


class PacketTag(Enum):  # Enumerate high level events that appear in Tenhou network packets
    """Packet tag keywords emitted by Tenhou logs."""  # Docstring summarising known packet tags

    INIT = "INIT"  # Round initialisation payload
    AGARI = "AGARI"  # Winning hand notification
    RYUUKYOKU = "RYUUKYOKU"  # Drawn hand (exhaustive draw) notification
    REACH = "REACH"  # Reach declaration event
    CALL = "N"  # General call meld event (chii, pon, kan)
    DORA = "DORA"  # Dora indicator reveal event
    DRAW = "DRAW"  # Tile draw notification when logs include DRAW
    DEAL = "DEAL"  # Tile deal notification for discard actions
    TSUMOHAI = "T"  # Self draw tile action identifier
    SHIMOHAI = "U"  # Lower seat draw tile action identifier
    TOIHAI = "V"  # Opposite seat draw tile action identifier
    KAMIHAI = "W"  # Upper seat draw tile action identifier
    BYE = "BYE"  # Disconnect or leave table notification
    RONKYOKU = "END"  # Hand end summary packet

    @classmethod  # Indicate the following helper operates at the class level
    def from_tag(cls, tag: str) -> "PacketTag":  # Convert a packet keyword string into a PacketTag member
        """Convert a raw packet keyword into a PacketTag enum member."""  # Docstring describing conversion behaviour
        normalized = tag.upper()  # Normalise incoming tag to uppercase for matching
        canonical = _PACKET_TAG_ALIASES.get(normalized, normalized)  # Resolve aliases or fall back to the tag itself
        try:  # Attempt to create a PacketTag from the canonical value
            return cls(canonical)  # Return the corresponding enum member
        except ValueError as exc:  # Handle cases where the tag is unknown
            raise ValueError(f"Unknown packet tag: {tag}") from exc  # Raise a descriptive error preserving context


_PACKET_TAG_ALIASES: Dict[str, str] = {  # Map alternate spellings to canonical packet tags
    "RYUKYOKU": PacketTag.RYUUKYOKU.value,  # Support alternative romanisation without the double U
    "AGARI_TSUMO": PacketTag.AGARI.value,  # Alias for combined naming found in some logs
    "AGARI_RON": PacketTag.AGARI.value,  # Alias variant indicating ron win
    "N": PacketTag.CALL.value,  # Ensure plain N resolves to the call event
    "DRAW": PacketTag.DRAW.value,  # Direct mapping for draw packets
    "DEAL": PacketTag.DEAL.value,  # Direct mapping for deal packets
    "T": PacketTag.TSUMOHAI.value,  # Ensure plain T resolves to the self draw action
    "U": PacketTag.SHIMOHAI.value,  # Ensure plain U resolves to the lower seat action
    "V": PacketTag.TOIHAI.value,  # Ensure plain V resolves to the opposite seat action
    "W": PacketTag.KAMIHAI.value,  # Ensure plain W resolves to the upper seat action
}  # End of alias dictionary definition


TAG_PATTERN = re.compile(r"<\s*(\w+)\s+([^>]*)>")  # Capture tag name and attribute blob from packet lines
ATTR_PATTERN = re.compile(r'(\w+)="([^"]*)"')  # Capture key="value" pairs

PacketAttributes = Dict[str, str]  # Alias describing the attribute dictionary extracted from packets
PacketHandler = Callable[[str], Any]  # Alias for handler callables that accept a packet line and return arbitrary data


class DrawType(IntEnum):  # Enumerate ways a tile can be discarded
    """Distinguish whether a discard was tedashi or tsumogiri."""  # Docstring describing the enum purpose

    TEDASHI = 0  # Tile taken from the hand
    TSUMOGIRI = 1  # Tile discarded immediately after draw


@dataclass  # Convert the class into a dataclass for automatic method generation
class Discard:  # Represent a single discard event with related metadata
    """Record for a single discard, including optional metadata."""  # Docstring summarising the stored information

    tile_id: int  # Logical 37-tile identifier aligned with assets/tiles/1.png..37.png
    draw_type: DrawType  # Whether the discard was tedashi or tsumogiri
    called: bool = False  # Flag indicating if the tile was called by another player
    tag: str | None = None  # Optional tag captured from network packets
    timestamp: float | None = None  # Optional epoch timestamp for ordering or analysis
    riichi_marker_before: bool = False  # Whether this discard carried the riichi declaration marker
    thinking_time_ms: float | None = None  # Time from the latest draw/call to this discard
    thinking_time_source: str | None = None  # Whether the thinking timer started on a draw or call
    thinking_time_before_reach_ms: float | None = None  # Time from the latest draw/call until REACH
    thinking_time_before_reach_source: str | None = None  # Whether the pre-REACH timer started on a draw or call
    self_hand_tiles_before_discard_136: List[int] = field(default_factory=list)  # Self concealed-hand snapshot at this discard timing
    lagged: int = 0  # 0..6 lag flag state defined by the capture pipeline
    lag_delay_ms: float | None = None  # Measured delay until the resolving draw/call packet


@dataclass  # Formalise the parsed AGARI data structure for downstream consumers
class AgariResult:  # Represent a normalised view over AGARI packet contents
    """Container holding a parsed AGARI event with typed fields."""  # Explain what the dataclass provides

    honba: Optional[int]  # 本場カウンタ (None when absent)
    riichi_sticks: Optional[int]  # 供託リーチ棒本数 (None when absent)
    hand_tiles: List[int]  # 和了者の手牌(副露牌除く、和了牌含む)
    meld_codes: List[str]  # 面子コード列（未デコードのまま保持）
    wait_tile: Optional[int]  # 和了牌 ID
    fu: Optional[int]  # 符 (None when情報未付帯)
    points_raw: Optional[int]  # 100 点単位の素点
    rank: Optional[int]  # 段位/満貫区分 (0-5)
    yaku: List[Tuple[int, int]]  # 役 ID と翻のペア
    yakuman: List[int]  # 役満 ID のリスト
    dora_indicators: List[int]  # 表ドラ表示牌 ID 群
    ura_indicators: List[int]  # 裏ドラ表示牌 ID 群
    winner_index: Optional[int]  # 和了者のインデックス (0-3)
    winner: Optional[Player]  # 和了者の Player 列挙体
    from_index: Optional[int]  # 放銃者/自摸元インデックス (0-3)
    from_player: Optional[Player]  # 放銃者/自摸元 Player 列挙体
    score_change: List[Tuple[int, int]]  # 終局時点の持点と増減
    is_tsumo: bool  # 自摸和かどうか
    raw_attrs: PacketAttributes  # オリジナルの属性辞書


@dataclass  # Make the tracker a dataclass for simpler initialization and representation
class SutehaiTracker:  # Manage discards per player seat
    """Helper that keeps track of discards for each player seat."""  # Docstring describing tracker responsibilities

    discards: Dict[Player, List[Discard]] = field(  # Dictionary storing lists of discards keyed by player
        default_factory=lambda: {player: [] for player in Player}  # Initialize each player key with an empty list
    )  # Finish field definition with custom default factory

    def add_discard(  # Method to record a new discard event
        self,  # Reference to the current tracker instance
        player: Player,  # Player who discarded the tile
        tile_id: int,  # Identifier of the discarded tile
        tsumogiri: bool = False,  # Whether this discard was a tsumogiri
        called: bool = False,  # Whether another player called this discard
        tag: str | None = None,  # Optional tag string for traceability
        timestamp: float | None = None,  # Optional timestamp marking when the discard occurred
        riichi_marker_before: bool = False,  # Whether this discard carried the riichi marker
    ) -> Discard:  # Method returns the Discard instance it creates
        """Append a discard for the given player and return the created record."""  # Docstring for method behaviour
        discard = Discard(  # Construct a Discard data object with the provided context
            tile_id=tile_id,  # Store which tile was discarded
            draw_type=DrawType.TSUMOGIRI if tsumogiri else DrawType.TEDASHI,  # Resolve discard type based on flag
            called=called,  # Store whether the tile resulted in a call
            tag=tag,  # Attach any optional tag string
            timestamp=timestamp,  # Record when the discard happened if available
            riichi_marker_before=riichi_marker_before,  # Keep the declaration marker for renderer/logic reuse
        )  # End of Discard construction
        self.discards[player].append(discard)  # Append the new discard to the list for the specified player
        return discard  # Return the newly created Discard instance to the caller

    def get_discards(self, player: Player) -> List[Discard]:  # Retrieve the discard list for a specific player
        """Return the chronological list of discards for a player."""  # Docstring describing what is returned
        return self.discards[player]  # Provide direct access to the stored list (caller should avoid mutating it)

    def players(self) -> Iterable[Player]:  # Enumerate the players known to the tracker
        """Iterate over all players tracked by this instance."""  # Docstring explaining the generator purpose
        return self.discards.keys()  # Yield the keys of the internal dictionary representing players


def extract_tag_and_attrs(packet_line: str) -> Optional[Tuple[str, PacketAttributes]]:  # Pull tag name and attributes from packet text
    """Extract the mjlog-like tag and its raw attributes from a packet line."""  # Document the helper
    match = TAG_PATTERN.search(packet_line)  # Search for a tag pattern in the incoming line
    if not match:  # Bail out when no tag is present
        return None  # Signal absence to the caller
    tag = match.group(1)  # Capture the tag name (e.g. AGARI)
    attr_blob = match.group(2)  # Capture the raw attribute string
    attributes = dict(ATTR_PATTERN.findall(attr_blob))  # Convert all key="value" pairs into a dictionary
    return tag, attributes  # Return tuple for downstream processing


def to_int_list(csv: str) -> List[int]:  # Convert comma-separated integers into a list
    """Convert a comma-separated string of integers into a list of ints."""  # Explain the utility
    if not csv:  # Short-circuit when the input is empty
        return []  # Return an empty list
    return [int(value) for value in csv.split(",") if value]  # Parse and filter out empty fragments


def to_fixed_pair(csv: str) -> Tuple[int, int]:  # Convert comma-separated 2-element string into a tuple
    """Convert a two-integer comma-separated string into a tuple."""  # Document behaviour
    values = to_int_list(csv)  # Reuse the helper to parse values
    if len(values) != 2:  # Validate length
        raise ValueError(f"Expected two integers but received: {csv}")  # Provide actionable error info
    return values[0], values[1]  # Return tuple


def parse_score_changes(csv: str) -> List[Tuple[int, int]]:  # Parse sc attribute representing score deltas
    """Parse the sc attribute into a list of (score, delta) tuples."""  # Describe the conversion
    values = to_int_list(csv)  # Build integer list
    if len(values) % 2 != 0:  # Ensure even count (pairs)
        raise ValueError(f"Score change field must contain pairs: {csv}")  # Deploy informative error
    pairs: List[Tuple[int, int]] = []  # Prepare result container
    for index in range(0, len(values), 2):  # Walk through value list in steps of two
        pairs.append((values[index], values[index + 1]))  # Append pair to output
    return pairs  # Return parsed list


def parse_yaku_pairs(csv: str) -> List[Tuple[int, int]]:  # Parse yaku attribute representing id/han pairs
    """Parse the yaku attribute into (yaku_id, han) tuples."""  # Describe conversion
    if not csv:  # Handle absence gracefully
        return []  # No yaku means empty list
    values = to_int_list(csv)  # Parse integers
    if len(values) % 2 != 0:  # Yaku should arrive in pairs
        raise ValueError(f"Yaku field must contain pairs: {csv}")  # Provide context for failing packets
    yaku_pairs: List[Tuple[int, int]] = []  # Prepare output
    for index in range(0, len(values), 2):  # Iterate pairwise
        yaku_pairs.append((values[index], values[index + 1]))  # Append pair to result
    return yaku_pairs  # Return pairs


def parse_yakuman_list(csv: str) -> List[int]:  # Parse yakuman attribute listing yakuman identifiers
    """Parse the yakuman attribute into a list of yakuman IDs."""  # Document behaviour
    return to_int_list(csv)  # Leverage the base helper directly


def parse_ten_values(csv: str) -> Tuple[int, int, int]:  # Parse ten attribute describing fu/points/rank
    """Parse the ten attribute into (fu, points_raw, rank)."""  # Explain the result
    values = to_int_list(csv)  # Parse integers
    if len(values) != 3:  # Ensure strict length
        raise ValueError(f"Ten field must contain three integers: {csv}")  # Provide context when failing
    return values[0], values[1], values[2]  # Return tuple of fu, points_raw, rank


def normalise_agari_attrs(attrs: PacketAttributes) -> AgariResult:  # Convert raw attribute dictionary into AgariResult
    """Normalise AGARI attributes into an AgariResult dataclass."""  # Document transformation
    honba: Optional[int] = None  # Initialise honba placeholder
    riichi_sticks: Optional[int] = None  # Initialise riichi stick placeholder
    if "ba" in attrs:  # ba attribute carries honba/riichi pair
        honba, riichi_sticks = to_fixed_pair(attrs["ba"])  # Parse honba/riichi
    fu: Optional[int] = None  # Prepare fu value
    points_raw: Optional[int] = None  # Prepare points
    rank: Optional[int] = None  # Prepare rank
    if "ten" in attrs:  # ten attribute summarises result
        fu, points_raw, rank = parse_ten_values(attrs["ten"])  # Parse components
    wait_tile = int(attrs["machi"]) if "machi" in attrs else None  # Convert machi when available
    winner_index = int(attrs["who"]) if "who" in attrs else None  # Determine winner index
    from_index = int(attrs["fromWho"]) if "fromWho" in attrs else None  # Determine source index
    hand_tiles = to_int_list(attrs.get("hai", ""))  # Collect winning hand tiles
    meld_codes = attrs.get("m", "").split(",") if attrs.get("m") else []  # Split meld codes
    yaku = parse_yaku_pairs(attrs.get("yaku", ""))  # Parse regular yaku
    yakuman = parse_yakuman_list(attrs.get("yakuman", ""))  # Parse yakuman list
    dora_indicators = to_int_list(attrs.get("doraHai", ""))  # Parse dora indicators
    ura_indicators = to_int_list(attrs.get("doraHaiUra", ""))  # Parse ura dora indicators
    score_change = parse_score_changes(attrs["sc"]) if "sc" in attrs else []  # Parse score changes when present
    is_tsumo = bool(  # Determine tsumo status by comparing winner and from indices
        winner_index is not None
        and from_index is not None
        and winner_index == from_index
    )  # End of boolean expression
    winner_player = Player.from_index(winner_index)  # Convert to Player enum (or None)
    from_player = Player.from_index(from_index)  # Convert to Player enum (or None)
    return AgariResult(  # Assemble dataclass with parsed values
        honba=honba,  # Store honba
        riichi_sticks=riichi_sticks,  # Store riichi sticks
        hand_tiles=hand_tiles,  # Store hand tiles
        meld_codes=meld_codes,  # Store meld codes
        wait_tile=wait_tile,  # Store wait tile
        fu=fu,  # Store fu
        points_raw=points_raw,  # Store raw points
        rank=rank,  # Store rank classification
        yaku=yaku,  # Store yaku pairs
        yakuman=yakuman,  # Store yakuman list
        dora_indicators=dora_indicators,  # Store dora indicators
        ura_indicators=ura_indicators,  # Store ura dora indicators
        winner_index=winner_index,  # Store winner index
        winner=winner_player,  # Store winner Player
        from_index=from_index,  # Store fromWho index
        from_player=from_player,  # Store fromWho Player
        score_change=score_change,  # Store score deltas
        is_tsumo=is_tsumo,  # Store tsumo flag
        raw_attrs=attrs,  # Keep raw attributes for reference
    )  # End dataclass construction


def handle_agari(packet_line: str) -> AgariResult:  # Handle AGARI packet lines
    """Parse an AGARI packet line and return a structured AgariResult."""  # Document handler
    extracted = extract_tag_and_attrs(packet_line)  # Extract tag and attributes
    if not extracted:  # Ensure the line contained a tag
        raise ValueError("Packet line does not contain an mjlog tag.")  # Provide actionable error
    tag, attrs = extracted  # Unpack tuple
    if tag != PacketTag.AGARI.value:  # Verify the tag matches AGARI
        raise ValueError(f"Expected AGARI tag but received: {tag}")  # Guard misuse
    return normalise_agari_attrs(attrs)  # Produce normalised result


def handle_init(packet_line: str) -> Optional[PacketAttributes]:  # Placeholder for INIT handling
    """Dispatch placeholder for INIT packet handling; extend with real logic as needed."""  # Document placeholder
    extracted = extract_tag_and_attrs(packet_line)  # Parse tag and attrs
    if not extracted:  # Return None when no tag present
        return None  # Signal absence
    tag, attrs = extracted  # Unpack
    if tag != PacketTag.INIT.value:  # Ensure correct tag
        raise ValueError(f"Expected INIT tag but received: {tag}")  # Guard against mismatched usage
    return attrs  # Return raw attrs for now (callers can expand)


def handle_reach(packet_line: str) -> Optional[PacketAttributes]:  # Placeholder for REACH handling
    """Dispatch placeholder for REACH packet handling; extend with score logic later."""  # Document placeholder
    extracted = extract_tag_and_attrs(packet_line)  # Parse line
    if not extracted:  # When no tag present
        return None  # Nothing to handle
    tag, attrs = extracted  # Unpack values
    if tag != PacketTag.REACH.value:  # Validate tag identity
        raise ValueError(f"Expected REACH tag but received: {tag}")  # Provide error context
    return attrs  # Return raw attrs for now


def handle_call(packet_line: str) -> Optional[PacketAttributes]:  # Placeholder for call (N) packets
    """Legacy CALL packet placeholder.

    Live packet capture decodes melds in `capture.meld_decoder` and `capture.fragment_parser`.
    This helper remains a raw-attribute parser for the older packet utility surface.
    """  # Document placeholder
    extracted = extract_tag_and_attrs(packet_line)  # Parse line
    if not extracted:  # No tag to work with
        return None  # Return None
    tag, attrs = extracted  # Unpack
    if tag != PacketTag.CALL.value:  # Validate expected tag
        raise ValueError(f"Expected call tag but received: {tag}")  # Provide error details
    return attrs  # Return raw data until decoding is implemented


def handle_draw(packet_line: str) -> Optional[PacketAttributes]:  # Placeholder for draw packets
    """Dispatch placeholder for DRAW packet handling; extend with tsumogiri detection later."""  # Document placeholder
    extracted = extract_tag_and_attrs(packet_line)  # Parse packet
    if not extracted:  # Without tag return None
        return None  # Nothing to dispatch
    tag, attrs = extracted  # Unpack tuple
    if tag != PacketTag.DRAW.value:  # Ensure draw tag
        raise ValueError(f"Expected DRAW tag but received: {tag}")  # Provide context
    return attrs  # Return raw attributes


def handle_deal(packet_line: str) -> Optional[PacketAttributes]:  # Placeholder for deal packets
    """Dispatch placeholder for DEAL packet handling; extend with discard updates later."""  # Document placeholder
    extracted = extract_tag_and_attrs(packet_line)  # Parse line
    if not extracted:  # Without tag return None
        return None  # No action
    tag, attrs = extracted  # Unpack tuple
    if tag != PacketTag.DEAL.value:  # Validate tag
        raise ValueError(f"Expected DEAL tag but received: {tag}")  # Provide error context
    return attrs  # Return data for downstream processing


EVENT_MAPPING: Dict[str, PacketHandler] = {  # Map packet tags to handler callables
    PacketTag.INIT.value: handle_init,  # Route INIT packets
    PacketTag.AGARI.value: handle_agari,  # Route AGARI packets
    PacketTag.REACH.value: handle_reach,  # Route REACH packets
    PacketTag.CALL.value: handle_call,  # Route call packets
    PacketTag.DRAW.value: handle_draw,  # Route draw packets
    PacketTag.DEAL.value: handle_deal,  # Route deal packets
}  # End of event mapping


def process_packet_line(packet_line: str) -> Optional[Any]:  # Process a single packet line and dispatch to handlers
    """Process a packet line by extracting its tag and dispatching to the mapped handler."""  # Describe dispatcher
    parsed = extract_tag_and_attrs(packet_line)  # Extract tag and attributes
    if not parsed:  # Exit early when no tag found
        return None  # No event to handle
    tag, _attrs = parsed  # Unpack tag (attributes unused here)
    handler = EVENT_MAPPING.get(tag)  # Find handler in mapping
    if not handler:  # Gracefully skip unknown tags
        return None  # Return None to indicate no handling took place
    return handler(packet_line)  # Invoke handler and bubble up its return value
