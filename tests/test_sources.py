import copy,hashlib,json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import refresh_sources as r

class SourceChecks(unittest.TestCase):
    def setUp(self):
        self.pdf=b'%PDF-1.4\nreviewed label'
        self.record={'reg':'1-2','name':'Example','status':'Active','restrictedUse':'No','signalWord':'Caution','latestDocument':'https://www3.epa.gov/pesticides/chem_search/ppls/000001-00002-20260101.pdf','ingredients':[{'pc_code':'1','active_ing_percent':10}],'source':'https://example.test/epa'}
        self.raw={'items':[{'eparegno':'1-2','productname':'Example','product_status':'Active','rup_yn':'No','signal_word':'Caution','active_ingredients':self.record['ingredients'],'pdffiles':[{'pdffile':'000001-00002-20260101.pdf','pdffile_accepted_date':'January 1, 2026'}]}]}
        self.data={'registry':[self.record],'products':[{'id':'p','name':'Example','reg':'1-2','rate':'5 fl oz/A','efficacy':'','labelUrl':'https://example.test/label.pdf','sha256':r.digest(self.pdf)}],'sources':[{'id':'uk','url':'https://kentuckypestnews.wordpress.com/canola/','modified':'2026-01-01'},{'id':'ut','url':'https://news.utcrops.com/canola/','modified':'2026-01-01'}]}
    def reader(self,url,binary=False):
        if binary:return self.pdf
        if url==self.record['source']:return copy.deepcopy(self.raw)
        if url==r.FEEDS['uk']:return {'found':1,'posts':[{'date':'2026-01-01','modified':'2026-01-01','title':'Canola white mold','URL':self.data['sources'][0]['url']}]}
        if url==r.FEEDS['ut']:return [{'date':'2026-01-01','modified':'2026-01-01','title':{'rendered':'Canola white mold'},'link':self.data['sources'][1]['url']}]
        raise AssertionError(url)
    def test_matches_do_not_change_reviewed_data(self):
        before=copy.deepcopy(self.data);s=r.refresh(self.data,reader=self.reader)
        self.assertEqual(self.data,before);self.assertEqual(s['epaChecks']['1-2']['status'],'matched');self.assertEqual(s['checks']['p']['status'],'matched');self.assertEqual(s['criticalChanges'],{});self.assertEqual(s['feedChecks']['uk']['status'],'matched')
    def test_new_label_status_and_ingredient_changes(self):
        self.raw['items'][0].update(product_status='Cancelled',active_ingredients=[{'pc_code':'2','active_ing_percent':20}])
        self.raw['items'][0]['pdffiles'].append({'pdffile':'000001-00002-20261116.pdf'})
        s=r.refresh(self.data,reader=self.reader)
        self.assertEqual(len(s['criticalChanges']['1-2']),3);self.assertEqual(s['liveRegistry']['1-2']['status'],'Cancelled');self.assertEqual(self.data['products'][0]['rate'],'5 fl oz/A')
    def test_prior_alerts_survive_all_network_failures(self):
        previous={'reviewedHash':r.baseline_hash(self.data),'criticalChanges':{'1-2':['Label changed']},'pdfAlerts':{'p':'PDF changed'}}
        def failed(*args,**kwargs):raise OSError('Unavailable')
        s=r.refresh(self.data,previous,reader=failed)
        self.assertEqual(s['criticalChanges'],previous['criticalChanges']);self.assertEqual(s['pdfAlerts'],previous['pdfAlerts']);self.assertEqual(s['checks']['p']['status'],'unavailable')
    def test_confirmed_matches_clear_previous_alerts(self):
        previous={'reviewedHash':r.baseline_hash(self.data),'criticalChanges':{'1-2':['Label changed']},'pdfAlerts':{'p':'PDF changed'}}
        s=r.refresh(self.data,previous,reader=self.reader)
        self.assertEqual(s['criticalChanges'],{});self.assertEqual(s['pdfAlerts'],{})
    def test_different_baseline_does_not_import_previous_metadata(self):
        previous={'reviewedHash':'old','criticalChanges':{'1-2':['Old warning']},'pdfAlerts':{'p':'Old warning'}}
        self.assertEqual(r.refresh(self.data,previous,reader=self.reader)['criticalChanges'],{})
    def test_missing_exact_registration_is_a_hold(self):
        self.raw['items'][0]['eparegno']='9-9'
        s=r.refresh(self.data,reader=self.reader)
        self.assertIn('1-2',s['criticalChanges']);self.assertEqual(s['epaChecks']['1-2']['status'],'unavailable')
    def test_invalid_content_does_not_become_a_match(self):
        def reader(url,binary=False):return b'<html>Error</html>'if binary else self.reader(url)
        self.assertEqual(r.refresh(self.data,reader=reader)['checks']['p']['status'],'unavailable')
    def test_changed_pdf_is_a_hold(self):
        def reader(url,binary=False):return b'%PDF-1.4\nchanged label'if binary else self.reader(url)
        self.assertIn('p',r.refresh(self.data,reader=reader)['pdfAlerts'])
    def test_only_approved_metadata_is_normalized(self):
        a=b'%PDF-1.4 /ModDate(D:20200101) xmp:ModifyDate="2020" /ID [<1234><4567>] rate 5'
        b=b'%PDF-1.4 /ModDate(D:20261116) xmp:ModifyDate="2026" /ID [<1234><7890>] rate 5'
        p={'sha256':r.digest(a),'normalizedSha256':r.digest(r.normalize_pdf(a)),'fingerprintMode':'syngenta-download-metadata-v1'}
        self.assertTrue(r.document_matches(p,b));self.assertFalse(r.document_matches(p,b.replace(b'rate 5',b'rate 9')));self.assertFalse(r.document_matches(p,b.replace(b'<1234>',b'<9999>')))
    def test_feed_change_enters_review_queue(self):
        def reader(url,binary=False):
            payload=self.reader(url,binary)
            if url==r.FEEDS['ut']:payload[0]['modified']='2026-11-16'
            return payload
        s=r.refresh(self.data,reader=reader)
        self.assertEqual(s['feedChecks']['ut']['status'],'changed');self.assertEqual(len(s['candidates']),1)
    def test_incomplete_feed_is_unverified(self):
        def reader(url,binary=False):
            payload=self.reader(url,binary)
            if url==r.FEEDS['uk']:payload['found']=1000
            return payload
        self.assertEqual(r.refresh(self.data,reader=reader)['feedChecks']['uk']['status'],'unavailable')
    def test_repeated_failures_stop_redundant_requests(self):
        data=copy.deepcopy(self.data)
        data['registry']=[dict(self.record,reg=f'1-{n}',source=f'https://example.test/epa/{n}')for n in range(20)]
        data['products']=[dict(self.data['products'][0],id=f'p{n}')for n in range(20)]
        calls={'epa':0,'pdf':0}
        def failed(url,binary=False):
            if binary:calls['pdf']+=1
            elif '/epa/'in url:calls['epa']+=1
            raise OSError('Unavailable')
        s=r.refresh(data,reader=failed,workers=1)
        self.assertEqual(calls,{'epa':6,'pdf':3})
        self.assertEqual(len(s['epaChecks']),20);self.assertEqual(len(s['checks']),20)
        self.assertTrue(all(v['status']=='unavailable'for v in s['epaChecks'].values()))

if __name__=='__main__':unittest.main()
