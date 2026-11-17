import unittest

from featurepipe.evidence import quote_audit


class EvidenceTests(unittest.TestCase):
    def test_quote_presence_is_not_attribution(self):
        result=quote_audit('乙说：“只借不卖。”他又说：“永远免费。”', [{"id":"S1","text":"甲说：只借不卖。"}])
        self.assertEqual(result['marked_quotes'],2)
        self.assertEqual(result['unmatched_quotes'],1)
        self.assertEqual(result['quotes'][0]['exact_source_ids'],['S1'])
        self.assertIn('does not verify attribution',result['scope'])

    def test_cannot_join_quotes_across_sources(self):
        result=quote_audit('“全部免费”', [{"id":"A","text":"全部"},{"id":"B","text":"免费"}])
        self.assertEqual(result['unmatched_quotes'],1)

    def test_end_punctuation_change_is_reported_separately(self):
        result=quote_audit('“只有两件，”甲说。', [{"id":"A","text":"甲说：只有两件。"}])
        self.assertEqual(result['unmatched_quotes'],1)
        self.assertEqual(result['unmatched_after_end_punctuation_adjustment'],0)
