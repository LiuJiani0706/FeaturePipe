import unittest
from featurepipe.client import BudgetExceeded
from featurepipe.spend import SpendGuard


class SpendTests(unittest.TestCase):
    def guard(self):return SpendGuard(1,{'M':{'input':10,'output':20,'cached_input':1}})

    def test_inflight_reservations_block_overspend(self):
        g=self.guard();r=g.reserve('M',50000,10000)
        with self.assertRaises(BudgetExceeded):g.reserve('M',50000,10000)
        g.finish('M',r,{'prompt_tokens':10000,'completion_tokens':1000,'prompt_cache_hit_tokens':8000})
        self.assertAlmostEqual(g.spent,0.048)
        self.assertAlmostEqual(g.held,0)

    def test_unknown_usage_consumes_reservation(self):
        g=self.guard();r=g.reserve('M',10000,1000);g.finish('M',r,None)
        self.assertAlmostEqual(g.spent,0.12)

    def test_resume_assumes_inflight_may_be_billed(self):
        g=self.guard();g.reserve('M',10000,1000)
        new=self.guard();new.restore(g.snapshot())
        self.assertAlmostEqual(new.spent,0.12)
        self.assertAlmostEqual(new.held,0)

    def test_writer_leaves_protected_reviewer_budget(self):
        g=self.guard()
        with self.assertRaises(BudgetExceeded):g.reserve('M',50000,10000,protected_remainder=0.4)
        reservation=g.reserve('M',50000,10000)
        self.assertAlmostEqual(reservation,0.7)

    def test_nonfinite_budget_and_boolean_usage_fail_safe(self):
        for value in (float('nan'),float('inf'),-1,0):
            with self.assertRaises(ValueError):SpendGuard(value,{'M':{'input':10,'output':20,'cached_input':1}})
        g=self.guard();reservation=g.reserve('M',10000,1000)
        g.finish('M',reservation,{'prompt_tokens':False,'completion_tokens':False})
        self.assertAlmostEqual(g.spent,reservation)
