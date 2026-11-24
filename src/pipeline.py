"""Reproducible synthetic product analytics case. Python standard library only."""
from pathlib import Path
import csv
import json
import math
import random
import sqlite3
from datetime import datetime, timedelta
from statistics import NormalDist
from html import escape

ROOT = Path(__file__).resolve().parents[1]
SEED = 24112026
END = datetime(2026, 10, 31, 23, 59, 59)

def stamp(value):
    return value.strftime('%Y-%m-%d %H:%M:%S')

def generate(db, size=12000):
    rng = random.Random(SEED)
    db.executemany('INSERT INTO acquisition_sources VALUES (?,?)', enumerate(['Organic', 'Sports media', 'Partner communities', 'Paid social'], 1))
    db.execute('INSERT INTO dataset_metadata VALUES (1,?,?)', (END.date().isoformat(), SEED))
    event_id = 0
    def event(uid, at, name, channel=None):
        nonlocal event_id
        if at <= END:
            event_id += 1
            db.execute('INSERT INTO events VALUES (?,?,?,?,?)', (event_id, uid, stamp(at), name, channel))
    for uid in range(1, size + 1):
        source = rng.choices([1,2,3,4], weights=[30,25,25,20])[0]
        registered = datetime(2026,8,1) + timedelta(days=rng.randrange(92), hours=rng.randrange(20))
        interest = rng.choice(['Football', 'Hockey', 'Basketball', None])
        consent = int(rng.random() < .85)
        db.execute('INSERT INTO users VALUES (?,?,?,?,?,?)', (uid, stamp(registered), source, interest, consent, consent))
        event(uid, registered + timedelta(minutes=1), 'article_opened')
        if interest:
            event(uid, registered + timedelta(minutes=2), 'interest_selected')
        if rng.random() > {1:.78,2:.70,3:.74,4:.57}[source]:
            continue
        first = registered + timedelta(minutes=5)
        event(uid, first, 'article_read')
        variant = None
        if consent and interest:
            variant = rng.choice(['email','community'])
            db.execute('INSERT INTO experiment_assignments VALUES (?,?,?)', (uid, stamp(first), variant))
            sent = first + timedelta(hours=1)
            event(uid, sent, 'communication_sent', variant)
            if variant == 'community' and rng.random() < .42:
                event(uid, sent + timedelta(hours=rng.randrange(1,48)), 'community_joined', variant)
            if rng.random() < (.035 if variant == 'community' else .025):
                event(uid, sent + timedelta(hours=rng.randrange(2,72)), 'communication_opted_out', variant)
        # The treatment effect is ASSUMED by construction, not discovered in real users.
        for day in range(1,15):
            probability = .38 * math.exp(-.10 * day)
            if variant == 'community':
                probability += .045
            if rng.random() < probability:
                event(uid, first.replace(hour=0, minute=0, second=0) + timedelta(days=day, hours=rng.randrange(24)), 'article_read')
    for day in range(92):
        date = (datetime(2026,8,1)+timedelta(days=day)).date().isoformat()
        for source, cost in [(1,0),(2,2500),(3,1800),(4,3500)]:
            db.execute('INSERT INTO acquisition_costs VALUES (?,?,?)', (source,date,cost))
    db.commit()

def rows(db, name):
    return [dict(row) for row in db.execute((ROOT/'sql'/name).read_text(encoding='utf-8'))]

def checks(db):
    tests = {
        'foreign_keys': db.execute('PRAGMA foreign_key_check').fetchall() == [],
        'no_events_before_registration': db.execute('SELECT count(*) FROM events e JOIN users u USING(user_id) WHERE e.event_at<u.registered_at').fetchone()[0] == 0,
        'no_events_after_cutoff': db.execute('SELECT count(*) FROM events WHERE event_at>?',(stamp(END),)).fetchone()[0] == 0,
        'assignment_at_first_read': db.execute("SELECT count(*) FROM experiment_assignments a WHERE assigned_at != (SELECT min(event_at) FROM events e WHERE e.user_id=a.user_id AND event_name='article_read')").fetchone()[0] == 0,
        'eligible_assignments': db.execute('SELECT count(*) FROM experiment_assignments a JOIN users u USING(user_id) WHERE email_consent=0 OR community_consent=0 OR sport_interest IS NULL').fetchone()[0] == 0,
        'communication_matches_assignment': db.execute("SELECT count(*) FROM events e LEFT JOIN experiment_assignments a USING(user_id) WHERE e.event_name='communication_sent' AND (a.user_id IS NULL OR e.channel!=a.variant OR e.event_at<a.assigned_at)").fetchone()[0] == 0,
    }
    if not all(tests.values()):
        raise AssertionError(tests)
    return tests

def experiment(groups):
    a,b = (next(g for g in groups if g['variant']==v) for v in ['email','community'])
    n1,n2 = a['n'],b['n']
    p1,p2 = a['retained']/n1,b['retained']/n2
    pooled=(a['retained']+b['retained'])/(n1+n2)
    se0=math.sqrt(pooled*(1-pooled)*(1/n1+1/n2))
    pvalue=math.erfc(abs((p2-p1)/se0)/math.sqrt(2))
    se=math.sqrt(p1*(1-p1)/n1+p2*(1-p2)/n2)
    diff=p2-p1
    counts={g['variant']:g['assigned_total'] for g in groups}
    total=sum(counts.values())
    chi=sum((n-total/2)**2/(total/2) for n in counts.values())
    # Fixed planning assumptions, specified independently of observed simulated outcomes.
    baseline=.19; target=.23; average=(baseline+target)/2
    z=NormalDist().inv_cdf(.975); power_z=NormalDist().inv_cdf(.8)
    required=math.ceil((z*math.sqrt(2*average*(1-average))+power_z*math.sqrt(baseline*(1-baseline)+target*(1-target)))**2/(target-baseline)**2)
    q1,q2=a['opted_out_n']/n1,b['opted_out_n']/n2
    qse=math.sqrt(q1*(1-q1)/n1+q2*(1-q2)/n2)
    return dict(difference=diff,ci_low=diff-1.96*se,ci_high=diff+1.96*se,p_value=pvalue,
                optout_difference=q2-q1,optout_ci_low=q2-q1-1.96*qse,optout_ci_high=q2-q1+1.96*qse,
                srm_p_value=math.erfc(math.sqrt(chi/2)),required_per_group=required,
                planning_baseline=baseline,planning_mde=.04,alpha=.05,power=.8)

def export(db, name, query):
    result=db.execute(query)
    with (ROOT/'data'/f'{name}.csv').open('w',newline='',encoding='utf-8-sig') as f:
        writer=csv.writer(f);writer.writerow([c[0] for c in result.description]);writer.writerows(result)

def dashboard(summary):
    def table(data):
        labels={'stage':'Этап','users':'Пользователи','day':'День','eligible':'Зрелая база','retained':'Вернулись','rate':'Retention','source_name':'Источник','registered':'Регистрации','activated':'Активации','activation_rate':'Конверсия','cost':'Расходы','cost_per_activation':'Стоимость активации','variant':'Группа','assigned_total':'Назначено','n':'Зрелая база D7','opted_out_n':'Отключили','d7':'D7 Retention','week_return':'Возврат за неделю','opt_out':'Доля отключений','cohort':'Когорта'}
        values={'registered':'Регистрация','opened':'Открытие','activated':'Первое чтение','experiment_eligible':'Подходят для теста'}
        def display(key,value):
            if key in ['rate','activation_rate','d7','week_return','opt_out']:return f'{value:.2%}'
            return values.get(str(value),str(value))
        keys=list(data[0]);return '<table><thead><tr>'+''.join('<th>'+escape(labels.get(k,k))+'</th>' for k in keys)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+escape(display(k,r[k]))+'</td>' for k in keys)+'</tr>' for r in data)+'</tbody></table>'
    retention=summary['retention']
    chart='<svg viewBox="0 0 720 220" role="img" aria-label="Retention by day">'
    for i,r in enumerate(retention):
        x=100+i*210;h=r['rate']*400
        chart+=f'<rect x="{x}" y="{180-h}" width="95" height="{h}" rx="6" fill="#187f8c"/><text x="{x}" y="{165-h}" font-size="18">{r["rate"]:.1%}</text><text x="{x}" y="207" font-size="17">D{r["day"]}</text>'
    chart+='</svg>'
    e=summary['experiment']
    content=f'''<!doctype html><html lang="ru"><meta charset="utf-8"><title>FanPulse | Analytics</title>
<style>body{{font:16px/1.6 Segoe UI,Arial;background:#f2f6f8;color:#173047;margin:0}}main{{max-width:1050px;margin:auto;padding:36px}}h1{{font-size:42px;margin:0}}h2{{margin-top:0}}section{{background:white;border-radius:14px;padding:26px;margin:22px 0;overflow:auto}}.tag{{color:#a44b19;font-weight:600}}table{{border-collapse:collapse;width:100%;font-size:14px}}td,th{{text-align:left;padding:10px;border-bottom:1px solid #dce6ed}}svg{{max-width:760px;width:100%}}@media print{{body{{background:white}}section{{break-inside:avoid}}}}</style>
<main><div class="tag">УЧЕБНЫЙ ПРОЕКТ · СИНТЕТИЧЕСКИЕ ДАННЫЕ</div><h1>FanPulse</h1><p>Удержание аудитории спортивного медиасервиса · август - октябрь 2026</p>
<section><h2>Обзор</h2><p>Регистраций: <b>{summary['users']:,}</b> · Событий: <b>{summary['events']:,}</b>. Активация - первое чтение материала не менее 30 секунд.</p>{table(summary['funnel'])}</section>
<section><h2>Возвращаемость</h2>{chart}<p>Каждая метрика использует только пользователей с полностью наблюдаемым целевым днём. Возврат означает чтение материала.</p>{table(retention)}</section>
<section><h2>Источники привлечения</h2><p>Расходы в условных рублях. Для Organic учтены только прямые расходы: 0; стоимость работы команды исключена.</p>{table(summary['sources'])}</section>
<section><h2>Когортный разрез</h2><p>Когорта - месяц первого чтения. Зрелость проверяется для каждого пользователя отдельно.</p>{table(summary['cohorts'])}</section>
<section><h2>Эксперимент: email / community</h2><p>ITT-анализ: сравнение по назначенной группе. Основная метрика - D7 Retention.</p>{table(summary['groups'])}<p>Разница: <b>{e['difference']*100:.2f} п.п.</b> · 95% ДИ [{e['ci_low']*100:.2f}; {e['ci_high']*100:.2f}] п.п. · p = {e['p_value']:.4f}.</p><p>Проверка соотношения групп (SRM): p = {e['srm_p_value']:.3f}. План: {e['required_per_group']} пользователей на группу при baseline 19%, MDE 4 п.п., α=5%, мощности 80%.</p></section>
<section><h2>Вывод</h2><p>В симуляции группа community показывает {'более высокое' if e['difference']>0 else 'более низкое'} удержание. Эффект заложен генератором (+4,5 п.п. к вероятности ежедневного возврата). Результат демонстрирует анализ, но не доказывает полезность механики в реальном продукте.</p><p>Отключения коммуникаций выросли на {e['optout_difference']*100:.2f} п.п., 95% ДИ [{e['optout_ci_low']*100:.2f}; {e['optout_ci_high']*100:.2f}] п.п. Это ограничивающая метрика: массовый запуск на основании роста retention рекомендовать нельзя. Интервал для неё разведочный, без поправки на множественные сравнения.</p><p>Следующий бизнес-шаг: добровольный пилот с реальными пользователями, заранее зафиксированными метриками, допустимым ростом отписок и размером выборки. Чаты, контент и канал оцениваются как единый пакет.</p></section>
<section><h2>Воспроизведение</h2><p>Из корня проекта: <code>python src/pipeline.py</code>. Данные, запросы и проверки входят в архив. Seed: {SEED}. Внешние ресурсы и подключение к сети для этого отчёта не нужны.</p></section></main></html>'''
    (ROOT/'output'/'dashboard.html').write_text(content,encoding='utf-8')

def main():
    for name in ['data','output']:(ROOT/name).mkdir(exist_ok=True)
    path=ROOT/'data'/'fanpulse.sqlite'
    # Rebuild only the explicit generated database inside this project.
    if path.exists():path.unlink()
    db=sqlite3.connect(path);db.row_factory=sqlite3.Row
    db.executescript((ROOT/'sql'/'01_schema.sql').read_text(encoding='utf-8'))
    generate(db)
    quality=checks(db)
    summary={k:rows(db,f) for k,f in [('funnel','02_funnel.sql'),('retention','03_retention.sql'),('sources','04_sources.sql'),('groups','05_experiment.sql'),('cohorts','06_cohorts.sql')]}
    summary.update(users=db.execute('SELECT count(*) FROM users').fetchone()[0],events=db.execute('SELECT count(*) FROM events').fetchone()[0],checks=quality)
    summary['experiment']=experiment(summary['groups'])
    for name in ['users','events','acquisition_sources','acquisition_costs','experiment_assignments','dataset_metadata']:
        export(db,name,f'SELECT * FROM {name}')
    for key in ['funnel','retention','sources','groups','cohorts']:
        with (ROOT/'output'/f'{key}.csv').open('w',newline='',encoding='utf-8-sig') as f:
            writer=csv.DictWriter(f,fieldnames=list(summary[key][0]));writer.writeheader();writer.writerows(summary[key])
    (ROOT/'output'/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    dashboard(summary)
    print(json.dumps({k:summary[k] for k in ['users','events','checks','groups','experiment']},ensure_ascii=False,indent=2))
    db.close()

if __name__=='__main__':main()
