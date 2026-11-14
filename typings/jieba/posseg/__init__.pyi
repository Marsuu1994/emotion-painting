from collections.abc import Iterator

class pair:
    word: str
    flag: str

def cut(sentence: str) -> Iterator[pair]: ...
