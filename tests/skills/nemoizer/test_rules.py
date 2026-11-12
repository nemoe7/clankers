"""nemoizer rule registry tests."""

import prose.detectors
from conftest import SCRIPT

import rules


def test_prose_and_test_ids_have_separate_domains():
  assert set(rules.RULE_IDS.values()) == {"NMO100", "NMO901"}
  assert rules.PROSE_RULE_IDS == {
    "dangling_conjunction": "STE001",
    "semicolon": "STE100",
    "sentence": "STE200",
    "nominalization": "STE300",
    "wordy_phrase": "STE400",
    "archaic_connector": "STE401",
    "passive": "STE901",
    "phrasal": "STE902",
    "ellipsis": "STE903",
    "compound_instruction": "STE904",
    "noun_cluster": "STE905",
    "synonym_cluster": "STE906",
    "compound_tense": "STE908",
    "inline_list": "STE909",
    "double_negative": "STE910",
    "staged_frame": "HMN100",
    "stacked_qualifier": "HMN200",
    "ai_vocabulary": "HMN300",
    "arrow": "HMN400",
    "chatbot_courtesy": "HMN500",
    "curly_quote": "HMN600",
    "negative_contrast": "HMN901",
    "aphorism": "HMN902",
    "rhetorical_setup": "HMN903",
    "repeated_opener": "HMN904",
    "prose_dash": "HMN905",
    "vague_attribution": "HMN906",
    "copula_avoidance": "HMN907",
    "bold_label_bullet": "HMN908",
    "consecutive_emoji": "HMN909",
    "self_narration": "HMN910",
    "paragraph": "NMP100",
    "comment_block": "NMP101",
    "padded_ui_label": "NMU100",
    "serial_comma": "NMO003",
    "the_density": "NMO902",
  }
  assert rules.TEST_RULE_IDS == {
    "output_text": "NMT100",
    "measurement": "NMT200",
    "timing_wait": "NMT300",
    "numeric_setting": "NMT400",
  }
  assert "NMT300" in rules.KNOWN_RULE_IDS
  assert "NMT300" in rules.ADVISORY_RULE_IDS
  assert rules.RESERVED_RULE_IDS == {"HMN000"}
  assert "HMN000" in rules.KNOWN_RULE_IDS
  assert not (
    {
      "P001",
      "P002",
      "P003",
      "P004",
      "T001",
      "T002",
      "N001",
      "N002",
      "N003",
      "NMO001",
      "NMO002",
      "STE002",
      "STE003",
      "STE004",
      "STE005",
      "NMP001",
      "NMT001",
      "NMT002",
    }
    & rules.KNOWN_RULE_IDS
  )


def test_references_follow_markdownlint_doc_layout():
  refs_dir = SCRIPT.parent.parent / "references"
  rules_md = (refs_dir / "rules.md").read_text(encoding="utf-8")
  assert "\n# Rules\n" in rules_md
  for code in sorted(rules.KNOWN_RULE_IDS - rules.RESERVED_RULE_IDS):
    assert f"\n## `{code}` - " in rules_md
    rule_file = refs_dir / f"{code.lower()}.md"
    assert rule_file.is_file(), f"missing {rule_file.name}"
    text = rule_file.read_text(encoding="utf-8")
    assert f"\n# `{code}` - " in text
    assert "\nTags: " in text
    assert "\nAliases: " in text
    assert "\nRationale: " in text


def test_rule_registry_has_unique_codes_and_family_keys():
  codes = [rule.code for rule in rules.RULES]
  assert len(codes) == len(set(codes))
  family_keys = [(rule.family, key) for rule in rules.RULES for key in rule.keys]
  assert len(family_keys) == len(set(family_keys))
  for rule in rules.RULES:
    assert bool(rule.keys) == (rule.family != "reserved"), rule.code
    assert not rule.line_scoped or rule.family == "prose", rule.code
  detector_keys = [key for key, _ in prose.detectors.DETECTORS]
  assert len(detector_keys) == len(set(detector_keys))
  assert set(detector_keys) <= set(rules.PROSE_RULE_IDS)
