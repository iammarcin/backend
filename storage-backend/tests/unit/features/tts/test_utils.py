from features.tts.utils import (
    convert_timestamp_to_date,
    merge_audio_chunks,
    split_text_for_tts,
    tune_text,
)


def test_tune_text_removes_actions_and_formats_punctuation():
    original = "Hello, world! *burps loudly* <inner_monologue>secret</inner_monologue>"
    tuned = tune_text(original)

    assert "burps" not in tuned
    assert "inner_monologue" not in tuned
    assert ".." in tuned


def test_split_text_for_tts_respects_limit():
    sentence = "Lorem ipsum dolor sit amet. " * 100
    chunks = split_text_for_tts(sentence, max_chars=120)

    assert all(len(chunk) <= 120 for chunk in chunks)
    assert "Lorem" in chunks[0]


def test_merge_audio_chunks_concatenates_without_pydub():
    first = b"abc"
    second = b"def"
    merged = merge_audio_chunks([first, second], output_format="pcm")

    assert merged == first + second


def test_convert_timestamp_to_date_formats_iso():
    timestamp = 1_700_000_000
    iso = convert_timestamp_to_date(timestamp)

    assert iso and iso.endswith("+00:00")
