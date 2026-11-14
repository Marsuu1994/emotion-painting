from emotion_painting.chunking import Chunk, split_into_chunks, split_sentences
from emotion_painting.constants import CHUNK_MAX_CHARS


def chunk_texts(text: str) -> list[str]:
    return [chunk.text for chunk in split_into_chunks(text)]


def test_each_paragraph_is_a_chunk_with_its_position_and_length() -> None:
    chunks = split_into_chunks("今天很开心。\nA quiet evening.")

    assert chunks == [
        Chunk(index=0, text="今天很开心。"),
        Chunk(index=1, text="A quiet evening."),
    ]
    assert [chunk.char_count for chunk in chunks] == [6, 16]


def test_blank_lines_and_surrounding_spaces_go() -> None:
    assert chunk_texts("  第一段  \n\n\n\n第二段\n   \n") == ["第一段", "第二段"]


def test_text_with_nothing_in_it_has_no_chunks() -> None:
    assert split_into_chunks("") == []
    assert split_into_chunks(" \n\n  ") == []


def test_urls_go_and_the_text_around_them_stays() -> None:
    text = "看了 https://example.com/a?b=1 这篇文章，also www.example.org/page today"

    assert chunk_texts(text) == ["看了  这篇文章，also  today"]


def test_a_url_stops_at_the_chinese_text_right_after_it() -> None:
    assert chunk_texts("链接https://example.com/x真的很有用") == ["链接真的很有用"]


def test_punctuation_case_and_emoji_stay_as_written() -> None:
    text = "太棒了!!! I CAN'T believe it... 😭😭 真的？！"

    assert chunk_texts(text) == [text]


def test_a_long_paragraph_splits_into_groups_of_whole_sentences() -> None:
    sentences = [
        f"这是第{number}句话，写得稍微长一点用来凑字数。" for number in range(40)
    ]
    paragraph = "".join(sentences)
    assert len(paragraph) > CHUNK_MAX_CHARS

    pieces = chunk_texts(paragraph)

    assert len(pieces) > 1
    assert all(len(piece) <= CHUNK_MAX_CHARS for piece in pieces)
    assert all(piece.endswith("。") for piece in pieces)
    assert "".join(pieces) == paragraph


def test_groups_are_packed_up_to_the_limit() -> None:
    sentence = "x" * 99 + "."
    paragraph = " ".join([sentence] * 7)

    pieces = chunk_texts(paragraph)

    assert pieces == [" ".join([sentence] * 3), " ".join([sentence] * 3), sentence]


def test_a_sentence_over_the_limit_stays_whole() -> None:
    long_sentence = "长" * (CHUNK_MAX_CHARS + 50) + "。"

    assert chunk_texts(long_sentence + "短句。") == [long_sentence, "短句。"]


def test_chunks_are_numbered_across_paragraphs() -> None:
    long_paragraph = "一句话。" * CHUNK_MAX_CHARS

    chunks = split_into_chunks(f"开头\n{long_paragraph}\n结尾")

    assert [chunk.index for chunk in chunks] == list(range(len(chunks)))
    assert chunks[0].text == "开头"
    assert chunks[-1].text == "结尾"


def test_sentences_end_after_a_whole_run_of_terminators() -> None:
    assert split_sentences("真的吗？！太好了!!! Wait... what? 好。") == [
        "真的吗？！",
        "太好了!!!",
        " Wait...",
        " what?",
        " 好。",
    ]


def test_a_dot_inside_a_number_or_a_name_does_not_end_a_sentence() -> None:
    assert split_sentences("跑了3.5公里。Updated to v1.2 today.") == [
        "跑了3.5公里。",
        "Updated to v1.2 today.",
    ]


def test_text_after_the_last_terminator_is_a_sentence() -> None:
    assert split_sentences("第一句。没有句号的结尾") == ["第一句。", "没有句号的结尾"]
