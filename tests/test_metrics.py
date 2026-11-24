"""Hand-calculated fixtures: maturity, exact-day retention and ITT."""
import sqlite3
import unittest
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from pipeline import experiment

class MetricsTest(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(':memory:');self.db.row_factory=sqlite3.Row
        self.db.executescript((ROOT/'sql/01_schema.sql').read_text(encoding='utf-8'))
        self.db.execute("INSERT INTO acquisition_sources VALUES(1,'test')")
        self.db.execute("INSERT INTO dataset_metadata VALUES(1,'2026-10-31',1)")
        for uid,date,variant in [(1,'2026-10-01','email'),(2,'2026-10-01','community'),(3,'2026-10-30','email')]:
            at=date+' 10:00:00'
            self.db.execute('INSERT INTO users VALUES(?,?,1,\'Football\',1,1)',(uid,at))
            self.db.execute('INSERT INTO events(user_id,event_at,event_name) VALUES(?,?,\'article_read\')',(uid,at))
            self.db.execute('INSERT INTO experiment_assignments VALUES(?,?,?)',(uid,at,variant))
        # User 1 returns exactly on D7. User 2 returns on D6 but never joins a community.
        for uid,at in [(1,'2026-10-08 09:00:00'),(2,'2026-10-07 09:00:00')]:
            self.db.execute('INSERT INTO events(user_id,event_at,event_name) VALUES(?,?,\'article_read\')',(uid,at))
    def tearDown(self):self.db.close()
    def query(self,name):return [dict(r) for r in self.db.execute((ROOT/'sql'/name).read_text(encoding='utf-8'))]
    def test_exact_day_and_maturity(self):
        day7=next(r for r in self.query('03_retention.sql') if r['day']==7)
        self.assertEqual((day7['eligible'],day7['retained'],day7['rate']),(2,1,.5))
    def test_itt_keeps_non_joiners_and_excludes_immature(self):
        groups={r['variant']:r for r in self.query('05_experiment.sql')}
        self.assertEqual((groups['email']['assigned_total'],groups['email']['n']),(2,1))
        self.assertEqual((groups['community']['n'],groups['community']['retained'],groups['community']['week_return']),(1,0,1.0))
    def test_cohort_matches_total(self):
        cohort=next(r for r in self.query('06_cohorts.sql') if r['day']==7)
        self.assertEqual((cohort['eligible'],cohort['retained']),(2,1))

class ExperimentTest(unittest.TestCase):
    def test_equal_rates_have_zero_effect(self):
        result=experiment([dict(variant=v,n=2000,retained=400,opted_out_n=40,assigned_total=2000) for v in ['email','community']])
        self.assertEqual(result['difference'],0)
        self.assertEqual(result['p_value'],1)
        self.assertEqual(result['srm_p_value'],1)
        self.assertLess(result['ci_low'],0)
        self.assertGreater(result['ci_high'],0)
    def test_swapping_outcomes_reverses_effect(self):
        groups=[dict(variant='email',n=2000,retained=380,opted_out_n=40,assigned_total=2100),dict(variant='community',n=2000,retained=460,opted_out_n=60,assigned_total=2100)]
        first=experiment(groups)
        groups[0]['variant'],groups[1]['variant']='community','email'
        second=experiment(groups)
        self.assertAlmostEqual(first['difference'],-second['difference'])
        self.assertAlmostEqual(first['p_value'],second['p_value'])
        self.assertAlmostEqual(first['ci_low'],-second['ci_high'])

if __name__=='__main__':unittest.main()
