"""Ensure a paper comparison cannot mistake quote agreement for resolved skill."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

PATH=Path(__file__).resolve().parents[1]/'examples/kalshi_20260915/compare.py'
spec=importlib.util.spec_from_file_location('kalshi_pilot_compare',PATH)
pilot=importlib.util.module_from_spec(spec); spec.loader.exec_module(pilot)


class PilotScoringTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        patcher=patch.object(pilot,'ROOT',self.root);patcher.start();self.addCleanup(patcher.stop)
        self.market={'status':'active','result':'','rules_primary':'An event before the deadline.','rules_secondary':''}
        self.record={'key':'fixture','ticker':'FIXTURE','series_ticker':'SERIES',
                     'market_response':{'data':{'market':self.market},'retrieved_at':'2026-09-18T00:00:00Z'},
                     'quote':{'captured_at':'2026-09-15T10:00:00Z','midpoint':0.4,'yes_bid':0.39,'yes_ask':0.41,'last_trade':0.45}}
        self.write('raw/baseline.json',{'records':[self.record]})
        baseline={'snapshot_file':'raw/baseline.json','snapshot_sha256':pilot.sha(self.root/'raw/baseline.json'),'records':[self.record]}
        self.write('baseline.json',baseline)
        self.write('evaluation_policy.json',{'baseline_sha256':pilot.sha(self.root/'baseline.json')})
        self.write('forecasts/fixture/question.json',{'id':'q','text':'Question','event_deadline':'2026-10-01T00:00:00Z'})
        forecast={'id':'forecast_fixture','question_id':'q','question_version':1,
                  'question':pilot.read(self.root/'forecasts/fixture/question.json'),'mode':'prospective','probability':0.7,
                  'issued_at':'2026-09-15T11:00:00Z','information_as_of':'2026-09-15T10:55:00Z'}
        self.write('forecasts/fixture/outputs/forecast.json',forecast)
        self.write('forecasts/fixture/outputs/sealed_result.json',{'probability':0.7,'files':{
            'forecast.json':pilot.sha(self.root/'forecasts/fixture/outputs/forecast.json')}})

    def write(self,name,value):
        p=self.root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(value))

    def resolution(self,**fields):
        rec=copy.deepcopy(self.record);rec['market_response']['data']['market'].update(**fields)
        self.write('raw/resolution-1.json',{'records':[rec]})

    def test_unresolved_disagreement_has_no_accuracy_score(self):
        data=pilot.build()
        self.assertEqual(data['summary']['matched_resolved_n'],0)
        self.assertIsNone(data['summary']['paired_mean_difference'])
        self.assertAlmostEqual(data['rows'][0]['probability_difference_pp'],30)

    def test_finalized_outcome_scores_same_frozen_midpoint(self):
        self.resolution(status='finalized',result='yes',settlement_ts='2026-09-17T00:00:00Z')
        post=copy.deepcopy(self.record);post['quote']['midpoint']=0.95
        self.write('raw/post_forecast-1.json',{'records':[post]})
        data=pilot.build()
        self.assertEqual(data['summary']['matched_resolved_n'],1)
        self.assertAlmostEqual(data['summary']['model_mean_brier'],0.09)
        self.assertAlmostEqual(data['summary']['market_mean_brier'],0.36)
        self.assertAlmostEqual(data['summary']['paired_mean_difference'],-0.27)

    def test_false_outcome_reverses_relative_performance(self):
        self.resolution(status='finalized',result='no',settlement_ts='2026-09-17T00:00:00Z')
        self.assertAlmostEqual(pilot.build()['summary']['paired_mean_difference'],0.33)

    def test_changed_rules_nonbinary_and_early_known_outcomes_are_excluded(self):
        for fields,state in [({'rules_secondary':'Changed','status':'finalized','result':'yes'},'rule_change_requires_review'),
                             ({'status':'finalized','result':'scalar'},'nonbinary_or_canceled_excluded'),
                             ({'status':'finalized','result':'yes','settlement_ts':'2026-09-15T09:00:00Z'},'known_before_forecast_excluded')]:
            self.resolution(**fields)
            data=pilot.build()
            with self.subTest(state=state):
                self.assertEqual(data['rows'][0]['state'],state)
                self.assertEqual(data['summary']['matched_resolved_n'],0)

    def test_tampered_forecast_and_baseline_are_rejected(self):
        p=self.root/'forecasts/fixture/outputs/forecast.json';original=p.read_text()
        p.write_text(original+' ')
        with self.assertRaisesRegex(AssertionError,'Changed sealed'):pilot.build()
        p.write_text(original)
        p=self.root/'baseline.json';p.write_text(p.read_text()+' ')
        with self.assertRaisesRegex(AssertionError,'Frozen baseline'):pilot.build()

    def test_artifact_body_without_id_uses_seal_identity(self):
        path=self.root/'forecasts/fixture/outputs/forecast.json'
        body=pilot.read(path);del body['id'];self.write(str(path.relative_to(self.root)),body)
        for field in ('files','sha256','hashes'):
            self.write('forecasts/fixture/outputs/sealed_result.json',{
                'probability':0.7,'forecast_id':'forecast_fixture',field:{'outputs/forecast.json':pilot.sha(path)}})
            with self.subTest(field=field):
                self.assertEqual(pilot.build()['rows'][0]['forecast_id'],'forecast_fixture')


if __name__=='__main__':unittest.main()
