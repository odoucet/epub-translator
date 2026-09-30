from libs.languages import detect_language, expected_length_ratio


def test_detect_latin_languages():
    """Test stopword based detection of Latin-script languages."""
    assert detect_language("The cat sat on the mat and looked at the dog, which was sleeping.") == "en"
    assert detect_language("Le chat est assis sur le tapis et regarde le chien qui dort dans la cuisine.") == "fr"


def test_detect_cjk_languages():
    """Test detection of Chinese and Japanese."""
    assert detect_language("这是一个关于人工智能的故事。") == "zh"
    assert detect_language("これは人工知能についての物語です。") == "ja"


def test_detect_unknown():
    """Test that an unclear text gives no language."""
    assert detect_language("") is None
    assert detect_language("1234 5678 ###") is None


def test_expected_length_ratio():
    """Test the expected length ratio of a language pair."""
    assert expected_length_ratio("en", "fr") == 1.15
    assert expected_length_ratio("fr", "en") < 1
    assert expected_length_ratio("en", "zh") < 0.5
    assert expected_length_ratio(None, "fr") is None
    assert expected_length_ratio("en", "klingon") is None
