from emotion_painting.chunking import Chunk, split_into_chunks
from emotion_painting.constants import IMAGERY_WORD_LIMIT
from emotion_painting.imagery import extract_imagery_words, find_candidate_words


def imagery_of(text: str) -> list[str]:
    return extract_imagery_words(split_into_chunks(text))


def test_chinese_keeps_nouns_place_words_and_time_words() -> None:
    candidates = list(find_candidate_words("晚上我在公园的湖边看到了一只猫"))

    assert {"晚上", "公园", "湖边", "猫"} <= set(candidates)
    assert not {"我", "在", "的", "看到", "了"} & set(candidates)


def test_english_drops_stopwords_and_short_words_and_lowers_case() -> None:
    candidates = list(
        find_candidate_words("The Rain kept falling on an old Harbour, so I ran")
    )

    assert candidates == ["rain", "kept", "falling", "old", "harbour", "ran"]


def test_english_contractions_are_stopwords_with_either_apostrophe() -> None:
    assert list(find_candidate_words("I don't know, they’re late")) == ["know", "late"]


def test_mixed_text_yields_both_languages_in_order() -> None:
    candidates = list(find_candidate_words("周末去了beach，看到sunset"))

    assert (
        candidates.index("周末")
        < candidates.index("beach")
        < candidates.index("sunset")
    )


def test_a_repeated_word_outranks_words_seen_once() -> None:
    words = imagery_of(
        "The lighthouse stood there. A lighthouse, again the lighthouse, and one gull."
    )

    assert words[0] == "lighthouse"


def test_occurrences_add_up_across_chunks() -> None:
    chunks = [
        Chunk(index=0, text="gull gull"),
        Chunk(index=1, text="harbour"),
        Chunk(index=2, text="harbour"),
        Chunk(index=3, text="harbour"),
    ]

    assert extract_imagery_words(chunks) == ["harbour", "gull"]


def test_equally_scored_words_keep_the_order_they_occur_in() -> None:
    assert imagery_of("gull harbour lantern") == ["gull", "harbour", "lantern"]


def test_at_most_the_limit_of_words_comes_back() -> None:
    words = imagery_of("gull harbour lantern meadow orchard pebble quarry river")

    assert len(words) == IMAGERY_WORD_LIMIT


def test_a_rarer_chinese_word_outranks_a_common_one() -> None:
    words = imagery_of("今天去看了灯塔")

    assert words.index("灯塔") < words.index("今天")


def test_text_without_candidates_has_no_imagery() -> None:
    assert imagery_of("I am so... 😭 !!!") == []
    assert extract_imagery_words([]) == []
