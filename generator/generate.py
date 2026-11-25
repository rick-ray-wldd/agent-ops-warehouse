#!/usr/bin/env python3
"""Synthetic data for the agent-ops warehouse: a multi-agent workflow's event stream.

Standard library only. Deterministic for a given params file (seeded RNG). Writes raw CSV batches the way an
upstream exporter would (one batch per day, loaded the next morning), with deliberate dirt that the staging
layer has to handle:

- duplicates: the same event_id delivered again in a later batch;
- late arrivals: an event that shows up one or two batches after the day it happened;
- malformed rows: extra records with a missing timestamp, a missing kind or an unparsable offset;
- mixed offsets: the same instant written as +00:00 or +08:00.

It also writes data/expected/metrics.json, computed in plain Python from the clean truth. The dbt tests compare
the marts with it, so the SQL is checked against an independent implementation.

usage: python3 generator/generate.py [--params generator/params.json] [--out data]
"""
import argparse
import csv
import datetime as dt
import json
import math
from pathlib import Path
import random

UTC = dt.timezone.utc
PLUS8 = dt.timezone(dt.timedelta(hours=8))
EVENT_COLUMNS = ['event_id', 'event_time', 'kind', 'actor_id', 'project_id', 'task_id', 'caused_by',
                 'gen_ai_system', 'gen_ai_request_model', 'gen_ai_usage_input_tokens',
                 'gen_ai_usage_output_tokens', 'loaded_at']
FILLER_KINDS = [('agent.working', 60), ('human.prompted', 20), ('agent.notified', 20)]
REWORK_STAGES = [('dispatch', 15), ('execution', 45), ('review', 40)]


def iso(ts, tz=UTC):
    return ts.astimezone(tz).isoformat(timespec='seconds')


def weighted(rng, pairs):
    total = sum(w for _, w in pairs)
    x = rng.uniform(0, total)
    for value, w in pairs:
        x -= w
        if x <= 0:
            return value
    return pairs[-1][0]


def quantile(values, q):
    """Linear interpolation between closest ranks, the same rule as DuckDB quantile_cont."""
    xs = sorted(values)
    if not xs:
        return None
    pos = (len(xs) - 1) * q
    lo, hi = math.floor(pos), math.ceil(pos)
    return xs[lo] + (xs[hi] - xs[lo]) * (pos - lo)


class World:
    def __init__(self, params):
        self.p = params
        self.rng = random.Random(params['seed'])
        self.start = dt.datetime.fromisoformat(params['start_date']).replace(tzinfo=UTC)
        self.events, self.presence, self.task_changes, self.rework = [], [], [], []
        self.seq = {'evt': 0, 'chg': 0, 'rwk': 0, 'hb': 0, 'task': 0}
        self.agents = {a['agent_id']: dict(a) for a in params['agents']}
        self.model_changes = sorted(params['model_changes'], key=lambda c: c['day'])

    def next_id(self, kind):
        self.seq[kind] += 1
        return f'{kind}_{self.seq[kind]:06d}'

    def model_at(self, agent_id, when):
        a = self.agents[agent_id]
        model, effort = a['model'], a['effort']
        for c in self.model_changes:
            if c['agent_id'] == agent_id and self.start + dt.timedelta(days=c['day']) <= when:
                model, effort = c['model'], c['effort']
        return a['provider'], model

    def event(self, when, kind, actor, project, task=None, caused_by=None):
        when = when.replace(microsecond=0)  # the CSV carries whole seconds; keep the truth identical
        row = {'event_id': self.next_id('evt'), 'event_time': when, 'kind': kind, 'actor_id': actor,
               'project_id': project, 'task_id': task, 'caused_by': caused_by,
               'gen_ai_system': None, 'gen_ai_request_model': None,
               'gen_ai_usage_input_tokens': None, 'gen_ai_usage_output_tokens': None}
        if actor != 'human' and kind.startswith(('agent.', 'review.', 'task.')):
            system, model = self.model_at(actor, when)
            row.update(gen_ai_system=system, gen_ai_request_model=model,
                       gen_ai_usage_input_tokens=self.rng.randint(500, 20000),
                       gen_ai_usage_output_tokens=self.rng.randint(100, 4000))
        self.events.append(row)
        return row

    def change(self, when, task, state, owner):
        when = when.replace(microsecond=0)
        self.task_changes.append({'change_id': self.next_id('chg'), 'task_id': task, 'changed_at': when,
                                  'state': state, 'owner_agent_id': owner})

    def by_role(self, role):
        return sorted(a for a, v in self.agents.items() if v['role'] == role)

    def task(self, day_start):
        rng, p = self.rng, self.p
        task = self.next_id('task')
        project = rng.choice(p['projects'])['project_id']
        coordinator = rng.choice(self.by_role('coordinator'))
        writer = rng.choice(self.by_role('writer'))
        reviewer = self.by_role('reviewer')[0]
        t = day_start + dt.timedelta(minutes=rng.randint(60, 14 * 60))
        self.event(t, 'task.dispatched', coordinator, project, task)
        self.change(t, task, 'inbox', coordinator)
        t += dt.timedelta(minutes=rng.randint(1, 20))
        self.change(t, task, 'working', writer)
        for _ in range(rng.randint(2, 5)):
            self.event(t + dt.timedelta(minutes=rng.randint(1, 30)), 'agent.working', writer, project, task)
        if rng.uniform(0, 100) < p['needs_decision_share_pct']:
            t += dt.timedelta(minutes=rng.randint(10, 60))
            ask = self.event(t, 'agent.needs_decision', writer, project, task)
            self.change(t, task, 'blocked', writer)
            mu = math.log(p['decision_wait_median_minutes'])
            t += dt.timedelta(minutes=rng.lognormvariate(mu, p['decision_wait_sigma']))
            self.event(t, 'human.decision', 'human', project, task, caused_by=ask['event_id'])
            self.change(t, task, 'working', writer)
        rounds, block_pct = 0, p['review_block_share_pct']
        while True:
            t += dt.timedelta(minutes=rng.randint(30, 240) if rounds == 0 else rng.randint(30, 120))
            self.event(t, 'agent.done', writer, project, task)
            self.change(t, task, 'review', writer)
            t += dt.timedelta(minutes=rng.randint(10, 90))
            if rounds < 2 and rng.uniform(0, 100) < block_pct:
                self.event(t, 'review.blocked', reviewer, project, task)
                self.rework.append({'rework_id': self.next_id('rwk'), 'at': t.replace(microsecond=0), 'task_id': task,
                                    'stage': weighted(rng, REWORK_STAGES)})
                self.change(t, task, 'working', writer)
                rounds, block_pct = rounds + 1, 10
                continue
            self.event(t, 'review.passed', reviewer, project, task)
            self.change(t, task, 'done', reviewer)
            return

    def day(self, i):
        rng, p = self.rng, self.p
        day_start = self.start + dt.timedelta(days=i)
        for _ in range(p['tasks_per_day']):
            self.task(day_start)
        humans_and_agents = sorted(self.agents) + ['human']
        for _ in range(p['filler_events_per_day']):
            kind = weighted(rng, FILLER_KINDS)
            actor = 'human' if kind == 'human.prompted' else rng.choice([a for a in humans_and_agents if a != 'human'])
            self.event(day_start + dt.timedelta(seconds=rng.randint(0, 86399)), kind, actor,
                       rng.choice(p['projects'])['project_id'])
        # Work blocks: heartbeats every few minutes; blocks are at least 30 minutes apart.
        lo, hi = p['work_block_minutes']
        cursor = day_start + dt.timedelta(minutes=rng.randint(30, 120))
        for _ in range(p['work_blocks_per_day']):
            length = rng.randint(lo, hi)
            beat = cursor
            while beat <= cursor + dt.timedelta(minutes=length):
                self.presence.append({'presence_id': self.next_id('hb'), 'at': beat.replace(microsecond=0), 'kind': 'heartbeat'})
                beat += dt.timedelta(minutes=p['heartbeat_minutes'], seconds=rng.randint(-30, 30))
            cursor = beat + dt.timedelta(minutes=rng.randint(30, 180))

    def build(self):
        for i in range(self.p['days']):
            self.day(i)
        self.events.sort(key=lambda e: (e['event_time'], e['event_id']))
        self.presence.sort(key=lambda h: h['at'])
        self.task_changes.sort(key=lambda c: (c['changed_at'], c['change_id']))


def batch_day(ts):
    return ts.astimezone(UTC).date()


def write_batches(world, out):
    """Raw CSV batches: one file per load day; dirt is added here, never to the truth used for metrics."""
    rng, dirt = random.Random(world.p['seed'] + 1), world.p['dirt']
    raw = out / 'raw'
    batches = {}

    def put(table, day, row):
        batches.setdefault((table, day), []).append(row)

    stats = {'duplicate_rows': 0, 'late_rows': 0, 'malformed_rows': 0, 'plus8_rows': 0}
    for e in world.events:
        day = batch_day(e['event_time'])
        if rng.uniform(0, 100) < dirt['late_arrival_pct']:
            day += dt.timedelta(days=rng.randint(1, 2))
            stats['late_rows'] += 1
        tz = PLUS8 if rng.uniform(0, 100) < dirt['plus8_offset_pct'] else UTC
        stats['plus8_rows'] += tz is PLUS8
        row = {**e, 'event_time': iso(e['event_time'], tz)}
        put('events', day, row)
        if rng.uniform(0, 100) < dirt['duplicate_pct']:
            put('events', day + dt.timedelta(days=1), dict(row))
            stats['duplicate_rows'] += 1
    for i in range(world.p['days']):
        day = (world.start + dt.timedelta(days=i)).date()
        for n in range(dirt['malformed_rows_per_day']):
            bad = {c: None for c in EVENT_COLUMNS}
            bad.update(event_id=f'evt_bad_{i:03d}_{n}', actor_id='agent_01', project_id='project_alpha')
            flaw = (i + n) % 3
            bad['kind'] = None if flaw == 1 else 'agent.working'
            if flaw == 0:
                bad['event_time'] = None
            elif flaw == 2:
                bad['event_time'] = f'{day.isoformat()}T12:00:00+99:99'
            else:
                bad['event_time'] = f'{day.isoformat()}T12:00:00+00:00'
            put('events', day, bad)
            stats['malformed_rows'] += 1
    for h in world.presence:
        put('presence', batch_day(h['at']), {**h, 'at': iso(h['at'])})
    for c in world.task_changes:
        put('task_changes', batch_day(c['changed_at']), {**c, 'changed_at': iso(c['changed_at'])})
    for r in world.rework:
        put('rework', batch_day(r['at']), {**r, 'at': iso(r['at'])})

    columns = {'events': EVENT_COLUMNS, 'presence': ['presence_id', 'at', 'kind'],
               'task_changes': ['change_id', 'task_id', 'changed_at', 'state', 'owner_agent_id'],
               'rework': ['rework_id', 'at', 'task_id', 'stage']}
    for (table, day), rows in sorted(batches.items()):
        loaded_at = iso(dt.datetime.combine(day + dt.timedelta(days=1), dt.time(0, 30), UTC))
        path = raw / table / f'batch_{day.isoformat()}.csv'
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('w', newline='') as f:
            w = csv.DictWriter(f, fieldnames=columns[table] + ([] if table == 'events' else ['loaded_at']))
            w.writeheader()
            for row in rows:
                w.writerow({**{k: ('' if v is None else v) for k, v in row.items()}, 'loaded_at': loaded_at})
    agents = [{'agent_id': a, 'role': v['role'], 'provider': v['provider']} for a, v in sorted(world.agents.items())]
    agents.append({'agent_id': 'human', 'role': 'human', 'provider': ''})
    write_csv(raw / 'agents.csv', ['agent_id', 'role', 'provider'], agents)
    history = [{'agent_id': a, 'valid_from': iso(world.start), 'model': v['model'], 'effort': v['effort']}
               for a, v in sorted(world.agents.items())]
    history += [{'agent_id': c['agent_id'], 'valid_from': iso(world.start + dt.timedelta(days=c['day'])),
                 'model': c['model'], 'effort': c['effort']} for c in world.model_changes]
    write_csv(raw / 'agent_model_changes.csv', ['agent_id', 'valid_from', 'model', 'effort'], history)
    write_csv(raw / 'projects.csv', ['project_id', 'domain'], world.p['projects'])
    return stats


def write_csv(path, columns, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=columns)
        w.writeheader()
        w.writerows(rows)


def reference_metrics(world, stats):
    """The answer key, from the clean truth. Days are UTC dates; minutes are floats rounded to 3 places."""
    r3 = lambda x: None if x is None else round(x, 3)
    by_id = {e['event_id']: e for e in world.events}
    waits = {}
    for e in world.events:
        if e['kind'] == 'human.decision' and e['caused_by']:
            ask = by_id[e['caused_by']]
            waits.setdefault(batch_day(ask['event_time']).isoformat(), []).append(
                (e['event_time'] - ask['event_time']).total_seconds() / 60)
    decision = [{'day': d, 'decisions': len(v), 'p50_minutes': r3(quantile(v, .5)), 'p90_minutes': r3(quantile(v, .9))}
                for d, v in sorted(waits.items())]
    gap = dt.timedelta(minutes=world.p['session_gap_minutes'])
    sessions, current = [], None
    for h in world.presence:
        if current and h['at'] - current[1] <= gap:
            current[1] = h['at']
        else:
            if current:
                sessions.append(current)
            current = [h['at'], h['at']]
    if current:
        sessions.append(current)
    per_day = {}
    for s, e in sessions:
        per_day.setdefault(batch_day(s).isoformat(), []).append((e - s).total_seconds() / 60)
    work = [{'day': d, 'sessions': len(v), 'total_minutes': r3(sum(v)), 'longest_minutes': r3(max(v))}
            for d, v in sorted(per_day.items())]
    counts = {}
    for e in world.events:
        counts[batch_day(e['event_time']).isoformat()] = counts.get(batch_day(e['event_time']).isoformat(), 0) + 1
    days = sorted(counts)
    volume = [{'day': d, 'events': counts[d],
               'rolling_7d_avg': r3(sum(counts[x] for x in days[max(0, i - 6):i + 1]) / len(days[max(0, i - 6):i + 1]))}
              for i, d in enumerate(days)]
    stages = {}
    for r in world.rework:
        stages[r['stage']] = stages.get(r['stage'], 0) + 1
    total = sum(stages.values())
    rework = [{'stage': s, 'rework_count': n, 'share_pct': round(100 * n / total, 2)} for s, n in sorted(stages.items())]
    first_working, last_done = {}, {}
    for c in world.task_changes:
        if c['state'] == 'working':
            first_working.setdefault(c['task_id'], c['changed_at'])
        if c['state'] == 'done':
            last_done[c['task_id']] = c['changed_at']
    cycles = [(last_done[t] - first_working[t]).total_seconds() / 60 for t in last_done if t in first_working]
    intervals = len(world.task_changes)
    return {'decision_wait_daily': decision, 'work_sessions_daily': work, 'event_volume_daily': volume,
            'rework_by_stage': rework,
            'task_cycle_time': {'tasks': len(cycles), 'p50_minutes': r3(quantile(cycles, .5)),
                                'p90_minutes': r3(quantile(cycles, .9))},
            'counts': {'events': len(world.events), 'task_state_intervals': intervals,
                       'tasks': len({c['task_id'] for c in world.task_changes}), **stats}}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--params', type=Path, default=Path(__file__).with_name('params.json'))
    ap.add_argument('--out', type=Path, default=Path(__file__).resolve().parents[1] / 'data')
    a = ap.parse_args(argv)
    world = World(json.loads(a.params.read_text()))
    world.build()
    stats = write_batches(world, a.out)
    metrics = reference_metrics(world, stats)
    (a.out / 'expected').mkdir(parents=True, exist_ok=True)
    (a.out / 'expected' / 'metrics.json').write_text(json.dumps(metrics, indent=2) + '\n')
    print(json.dumps(metrics['counts']))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
