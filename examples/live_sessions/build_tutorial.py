"""Build the static tutorial from one captured CLI run; no network access."""
import html
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / 'docs'
RUN = DOCS / 'assets/session-run'
summary = json.loads((RUN / 'summary.json').read_text())
escape = html.escape
counter = 0


def pretty(value):
    return escape(json.dumps(value, indent=2))


def code(value, label='Terminal'):
    global counter
    counter += 1
    return f'<div class="code-block"><div class="code-heading"><span>{escape(label)}</span><button class="copy" type="button" data-copy="code-{counter}">Copy</button></div><pre><code id="code-{counter}">{escape(value)}</code></pre></div>'


def command(name, text, keys=None):
    record = json.loads((RUN / f'{name}.json').read_text())
    output = record['output']
    if keys:
        output = {k: output['data'][k] for k in keys}
    label = 'Selected data fields from the captured response.' if keys else 'Complete captured response.'
    return code(text) + f'<details class="command-output"><summary>Show command output</summary><div class="details-body"><p class="caption">{label} Measured command time: {record["elapsed_seconds"]:.4f} s. <a href="assets/session-run/{name}.json">Full execution record</a>.</p><pre>{pretty(output)}</pre></div></details>'


def input_file(name, selected=None):
    value = json.loads((RUN / 'inputs' / f'{name}.json').read_text())
    if selected:
        value = selected(value)
    return f'<details><summary>Inspect {name}.json{ " (excerpt)" if selected else ""}</summary><div class="details-body"><pre>{pretty(value)}</pre><a href="assets/session-run/inputs/{name}.json">Captured input file</a></div></details>'


sections = []

def section(id, label, title, body):
    sections.append((id, label, f'<section class="section" id="{id}"><p class="eyebrow">{label}</p><h2>{title}</h2>{body}</section>'))

p = 'vorhersage --project ./forecast-study '
section('example', 'The worked example', 'One question. Two forecasters. A record of the whole run.', '''
<p>Will a fictional factory ship by tomorrow’s deadline? We register this question, give each forecaster its own research session, pause while a tool is waiting, resume, freeze the forecasts, and score them after recording an outcome.</p>
<p>The two forecasters are small Python fixtures: arm <code>a</code> always submits 25%; arm <code>b</code> always submits 75%. Each runs twice. Their research returns a fictional readiness report. These authored choices make the mechanics reproducible without API keys. They do not test a model’s forecasting skill.</p>
<div class="table-scroll"><table><caption>Design fixed before execution</caption><thead><tr><th>Choice</th><th>This run</th><th>Why it matters</th></tr></thead><tbody>
<tr><td>Instrument</td><td>One versioned question; unconditional probability</td><td>Every session answers the same event.</td></tr>
<tr><td>Replication</td><td>Two arms × two whole sessions</td><td>The session is the unit of repetition.</td></tr>
<tr><td>Research</td><td>Independent live evidence; one page receipt and a readiness assessment per session</td><td>Evidence arrives during execution and is preserved.</td></tr>
<tr><td>Outcome</td><td>Authored YES, recorded after finalization</td><td>The scoring stage uses a later record.</td></tr>
</tbody></table></div>
<p>In a real study, the workers would call the chosen model and research services. Vorhersage supplies registration, durable execution, evidence records, validation, reports, and evaluation. Configuring a worker is part of the study.</p>
<div class="note"><strong>What will match on your machine.</strong> The probabilities, four completed sessions, and Brier scores are deterministic. IDs, timestamps, absolute paths, and runtime will differ. The captured run used the current source checkout, including its new session commands; the <a href="assets/session-run/summary.json">run manifest</a> records source hashes. Dollar amounts inside worker receipts are synthetic accounting inputs. Actual provider cost was $0.</div>
''')
section('setup', '01 / Get ready', 'Start with the runnable example.', '''
<p>Use Python 3.11 or newer and a checkout of Vorhersage containing <code>session-study</code>. From that checkout’s root, install the package in a virtual environment. If it is already installed in your active environment, continue with the example download.</p>
<details><summary>Install from a source checkout</summary><div class="details-body">''' + code('python3 -m venv .venv') + code('source .venv/bin/activate') + code('python -m pip install -e .') + '''<p>Use <code>vorhersage session-study --help</code> to check that this checkout includes the study runner.</p></div></details>
<p><a href="assets/session-tutorial.zip" download>Download the two-file example</a>, save it as <code>session-tutorial.zip</code> in your working directory, and extract it:</p>''' + code('python -m zipfile -e session-tutorial.zip session-tutorial') + '''
<p>The archive contains <a href="assets/session-tutorial/prepare.py">prepare.py</a>, which writes dated JSON inputs and reads saved receipts, and <a href="assets/session-tutorial/worker.py">worker.py</a>, which supplies deterministic model and tool responses. Keep the same working directory and Python environment throughout this tutorial.</p>
<p>The helper creates a new <code>forecast-study</code> directory. Choose a fresh destination; it deliberately refuses to reuse one.</p>''' + command('prepare-inputs', 'python session-tutorial/prepare.py inputs ./forecast-study') + '''
<details><summary>Give this walkthrough to an agent</summary><div class="details-body">''' + code('Run the Vorhersage session-study tutorial using the downloaded prepare.py and worker.py. Register both arms before execution, capture the waiting state, resume the same study, audit all sessions, export comparison.html, then record the synthetic outcome and evaluate. Preserve CLI receipts and report actual versus fixture costs separately.', 'Agent prompt') + '</div></details>')
section('register-question', '02 / Define the event', 'Make the probability unambiguous.', '''
<p>Initialize the project that will hold the questions, immutable artifacts, session history, and outcomes. The global <code>--project</code> argument selects this same directory for every CLI command.</p>''' + command('init', p + 'init --name "Forecasting tutorial"') + '''
<p>The helper wrote explicit YES, NO, and void rules and a deadline tomorrow. This is a simulation, with a fictional dispatch source. Register that file to fix version 1 of the question.</p>''' + command('question', p + 'question add --from ./forecast-study/question.json') + input_file('question') + '''
<p>Next register the unconditional condition: no added assumptions about the world. Save the returned envelope so the helper can use the actual condition ID in the study specification.</p>''' + command('condition', p + 'condition add --from ./forecast-study/condition.json > ./forecast-study/condition-result.json') + '<p class="caption">The response shown above is the JSON written to the file by the redirect.</p>')
section('register-study', '03 / Register the design', 'Freeze the comparison before it starts.', '''
<p>The study combines a shared question template with two arms and two repetitions. The helper inserts this run’s condition ID, current information cutoff, and absolute paths to the worker. It writes the specification; registration happens in the next native command.</p>''' + command('prepare-study', 'python session-tutorial/prepare.py study ./forecast-study') + input_file('study', lambda v: {k: v[k] for k in ['id','repetitions','order_seed','evidence_policy','session_template']}) + '''
<p>Each arm permits at most five model calls, five tool attempts, and $1 of reported usage per session. It requires a successful tool receipt, one unique page, and an assessment of readiness. The model worker’s only difference between arms is the authored probability.</p>''' + input_file('study', lambda v: {'arms':v['arms']}) + '''
<p><code>independent_live</code> lets each session collect its own evidence. A real comparison under this policy can differ because of both model behavior and research results. A frozen evidence study would answer a different methodological question.</p>''' + command('register', p + 'session-study add --from ./forecast-study/study.json > ./forecast-study/study-result.json') + '''
<p>Use the returned <code>data.study_id</code> wherever <code>STUDY_ID</code> appears below. <code>SESSION_ID</code> means the first trial’s session ID from the status response in the next step. Do not copy the captured run’s IDs into your own project.</p>''')
section('run', '04 / Research and resume', 'A waiting tool is part of the record.', '''
<p>Give the runner five controller steps. The seeded schedule visits all four sessions to queue research, then starts the first tool. This fixture deliberately returns <code>waiting</code> on its first tool invocation.</p>''' + command('first-run', p + 'session-study run STUDY_ID --max-steps 5', ['study_id','complete','next_position','usage']) + '''
<p><code>--max-steps</code> bounds controller visits, including polls; it is separate from each session’s model, tool, and dollar budgets. Inspect the study and the first trial’s session to see what remains unfinished.</p>''' + command('status', p + 'session-study status STUDY_ID', ['complete','next_position','trials']) + command('waiting', p + 'session show SESSION_ID', ['session_id','disposition','revision','usage','unknown_usage_attempts']) + '''
<p>The pending tool has no final usage receipt yet. Its attempt ID and continuation have already been saved. Run the same study again: the runner polls that attempt and completes the remaining work.</p>''' + command('resume', p + 'session-study run STUDY_ID --max-steps 20', ['complete','usage']) + '''
<p>All four sessions now have one forecast cell and a finalization record. Together they report eight fixture model calls and four fixture tool attempts. Polling does not create a second billable attempt in the ledger.</p>
<div class="trace-view"><p class="eyebrow">Explore the captured first session</p><label for="trace-event">Recorded event</label><select id="trace-event">''' + ''.join(f'<option value="{i}"{ " selected" if i==4 else ""}>Revision {e["revision"]} · {e["kind"]}</option>' for i,e in enumerate(summary['trace'])) + '''</select><p id="trace-explanation" aria-live="polite"></p><pre id="trace-payload"></pre></div>
<p class="caption">Actual event payloads from this run. Start-event request bodies are omitted in this view. Revisions 5 and 6 share a tool attempt ID: waiting, then completed. Submissions and finalization are separate immutable records.</p>
<p>A worker refusal or exhausted budget remains visible as a terminal disposition. An interrupted attempt with uncertain usage requires reconciliation before more work can be authorized. Resuming a study does not silently change the protocol or increase its budget.</p>''')
section('audit', '05 / Inspect the research', 'Completion and protocol fidelity answer different questions.', '''
<p>The audit asks whether the session filled the grid, satisfied its research requirements, and reported observations matching the registered protocol. Inspect the first session:</p>''' + command('audit', p + 'session audit SESSION_ID', ['protocol_fidelity','research','complete_grid','disposition','usage','requirements']) + '''
<p>The page receipt references a captured packet and its <code>status</code> record. The readiness assessment references that same evidence. The protocol observation says zero network calls, matching the fixture requirement.</p>
<p><strong>Read “matched” in context:</strong> the observation’s basis is <code>worker_reported</code>. Matching that report against the registered requirement is not independent verification. Likewise, counting a page establishes coverage, not research quality. Here the packet explicitly labels its contents synthetic.</p>
<p>For the whole comparison, export a self-contained HTML report. It retains each session’s status, usage, audit, probabilities, and evidence references.</p>''' + command('report', p + 'session-study report STUDY_ID --output ./forecast-study/comparison.html') + '''
<p><a class="button" href="assets/session-run/comparison.html">Open the captured comparison →</a></p><p class="caption">The report’s dollar column contains fixture usage, totaling $0.10. No money was spent on these workers. Its one row represents one shared question–condition cell, with four session forecasts.</p>''')
section('score', '06 / Resolve and evaluate', 'Keep the outcome after the forecasts.', '''
<p>Once every session is finalized, the helper writes a forecast cutoff, then a later synthetic YES outcome. This is an authored simulation resolution; the readiness packet cited by the fixture is not evidence that a real shipment occurred. The outcome file was unavailable to the workers during their run.</p>''' + command('prepare-resolution', 'python session-tutorial/prepare.py resolution ./forecast-study') + input_file('resolution') + '''
<p>Record the outcome with the native resolution command.</p>''' + command('resolve', p + 'resolve --from ./forecast-study/resolution.json') + '''
<p>Prepare an evaluation policy selecting all four sessions, the saved forecast cutoff, and an outcome cutoff after resolution. <code>allow_source_reported: false</code> keeps this evaluation tied to locally recorded timing.</p>''' + command('prepare-evaluation', 'python session-tutorial/prepare.py evaluation ./forecast-study') + input_file('evaluation') + '''
<p>Evaluate the eligible unconditional forecasts on their common resolved question. The evaluator records its policy, selected inputs, and exclusions with the result.</p>''' + command('evaluate', p + 'session evaluate --from ./forecast-study/evaluation.json', ['evaluation_id','arms','exclusions']) + '''
<div class="score-lab"><p class="eyebrow">Explore the scoring rule</p><label for="outcome">Outcome for this calculation</label><select id="outcome"><option value="1">YES — captured outcome</option><option value="0">NO — hypothetical alternative</option></select>
<div class="table-scroll"><table><caption>Brier score = (probability − outcome)² · lower is better</caption><thead><tr><th>Arm</th><th>Probability</th><th>Mean session Brier</th></tr></thead><tbody><tr><td>a · two sessions</td><td>25%</td><td id="score-a">0.5625</td></tr><tr><td>b · two sessions</td><td>75%</td><td id="score-b">0.0625</td></tr></tbody></table></div><p id="score-explanation" aria-live="polite">With YES, arm b is closer to the outcome.</p></div>
<p class="caption">Changing this control only recalculates the illustration. It does not alter the saved resolution or evaluation.</p>
<p>Under the captured YES outcome, <code>(0.75 − 1)² = 0.0625</code>. Both repetitions in each arm are identical, so averaging their scores leaves the score unchanged. This is <strong>one resolved event</strong>, not four independent observations. It establishes that the workflow and scoring work; it cannot establish comparative forecasting skill or calibration.</p>
<p>Conditional forecasts need a suitable conditional evaluation design. This evaluator scores unconditional cells; a complete conditional grid is not automatically an accuracy benchmark.</p>''')
section('verify', '07 / Keep the receipts', 'Leave an inspectable project behind.', '''
<p>Finish by checking SQLite integrity and the stored artifact hashes.</p>''' + command('doctor', p + 'doctor') + f'''
<p>This capture checked {summary['doctor']['artifacts_checked']} artifacts. The complete execution took <strong>{summary['elapsed_seconds']:.3f} seconds</strong>, measured from input preparation through the integrity check on September 12, 2026. Installation, downloads, and building this page are outside that timer. Actual provider calls: <strong>0</strong>. Actual provider cost: <strong>$0</strong>.</p>
<div class="table-scroll"><table><caption>Files to retain</caption><thead><tr><th>Artifact</th><th>Purpose</th></tr></thead><tbody>
<tr><td>Your forecast-study directory</td><td>The native project, immutable artifacts, receipts, inputs, and exported report. Keep the whole directory.</td></tr>
<tr><td><a href="assets/session-run/comparison.html">comparison.html</a></td><td>Portable, interactive comparison of forecasts and execution records.</td></tr>
<tr><td><a href="assets/session-run/evaluate.json">Evaluation receipt</a></td><td>Policy, selected forecasts, exclusions, and arm scores from this run.</td></tr>
<tr><td><a href="assets/session-run/summary.json">Capture manifest</a></td><td>Timing, costs, source hashes, fixture hashes, and the displayed event trace.</td></tr>
</tbody></table></div>
<p>To regenerate the published receipts from a checkout, run the capture script with a fresh destination. It executes the same sequence of CLI operations, asserting the waiting state, completed study, and expected scores.</p>''' + code('python examples/live_sessions/capture_tutorial.py ./tutorial-capture') + '''
<p>Then rebuild this static page and its downloadable kit from those receipts:</p>''' + code('python examples/live_sessions/build_tutorial.py'))
section('real-study', 'Next / Reproduce a real study', 'Replace the fixture with a declared research protocol.', '''
<p>The AIRO replication motivated this session workflow: a model researches and answers an entire instrument in one continuing conversation. Reproducing it means preserving more than the final probability table. The model settings, conversation, tools, stopping rules, evidence timing, and failures all matter.</p>
<div class="table-scroll"><table><caption>From this example to the AIRO workflow</caption><thead><tr><th>In this tutorial</th><th>In the replication</th></tr></thead><tbody>
<tr><td>One unconditional question</td><td>Register the paper’s questions, horizons, conditions, and coherence relations as one instrument.</td></tr>
<tr><td>Two fixed Python responders</td><td>Declare a model and transport per arm, with its reasoning settings, output limits, and full conversation records.</td></tr>
<tr><td>One fictional page</td><td>Implement search and page-reading workers; retain queries, results, retrieved text, and source-linked assessments.</td></tr>
<tr><td>One readiness requirement</td><td>Register the authors’ research and effort requirements before execution; audit observations and record deviations.</td></tr>
<tr><td>An authored YES outcome</td><td>Separate reproduction of saved analyses from prospective scoring. Many long-horizon outcomes remain unresolved.</td></tr>
</tbody></table></div>
<p>Firecrawl is optional: the package’s worker contract is service-independent. The authors’ protocol uses Tavily. Match that protocol when reproducing their experiment; a different research service defines a changed configuration that should be recorded.</p>
<p>The existing AIRO example and its replication notes cover the saved-output checks and subsequent model runs. Those are separate studies from the synthetic capture on this page. EDSL transport improvements are tracked in <a href="https://github.com/expectedparrot/edsl/issues/2642">reasoning settings</a>, <a href="https://github.com/expectedparrot/edsl/issues/2643">Anthropic streaming</a>, and <a href="https://github.com/expectedparrot/edsl/issues/2644">native session support</a>; this tutorial does not imply that those changes have shipped.</p>
<div class="resource-links"><a href="https://github.com/expectedparrot/vorhersage/blob/main/docs/AIRO_REPLICATION.md">AIRO replication notes ↗</a><a href="https://github.com/expectedparrot/vorhersage/blob/main/docs/LIVE_SESSIONS.md">Worker protocol, budgets, and recovery ↗</a><a href="https://github.com/expectedparrot/vorhersage/blob/main/examples/airo/README.md">The larger worked replication ↗</a><a href="single-question.html">Single-question tutorial: evidence, revisions, and scenarios →</a></div>
''')
nav = ''.join(f'<a href="#{id}">{label}</a>' for id,label,_ in sections)
page = '''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="description" content="An executed Vorhersage tutorial: register a forecasting study, research, resume sessions, compare forecasts, and score outcomes."><meta name="theme-color" content="#173e35"><title>Vorhersage — A forecasting study, from start to score</title><link rel="stylesheet" href="site.css"><script src="site.js" defer></script></head><body class="study-tutorial">
<a class="skip" href="#main">Skip to content</a><header class="site-header"><a class="wordmark" href="#"><span class="mark" aria-hidden="true">V<span>↗</span></span> Vorhersage</a><nav aria-label="Primary"><a href="examples/nyc-2026-09-16/">NYC live example</a><a href="#setup">Run the example</a><a href="https://github.com/expectedparrot/vorhersage">GitHub ↗</a></nav></header>
<main id="main"><section class="hero" aria-labelledby="hero-title"><div><p class="eyebrow">Expected Parrot / A worked forecasting study</p><h1 id="hero-title">From a question<br><em>to a scored forecast.</em></h1><p class="lead">Register a comparison, preserve the research, resume unfinished work, and evaluate the result. Follow one complete run through Vorhersage.</p><div class="actions"><a class="button" href="assets/session-run/comparison.html">See the finished report →</a><a class="text-link" href="#setup">Recreate this run</a></div><p class="meta">Python 3.11+ · Offline example · No API keys</p><p class="note"><strong>A live research case:</strong> <a href="examples/nyc-2026-09-16/">Read the NYC temperature forecast</a> — evidence, methodology flowchart, model assumptions, and a sealed prediction compared with Kalshi. <a href="examples/nyc-2026-09-16/full-report.pdf">Download PDF</a>.</p></div>
<figure class="result-preview"><figcaption class="eyebrow">Captured result / synthetic forecasts</figcaption><p class="preview-question">Will the fictional factory ship?</p><div class="preview-row"><span>Arm a</span><div class="preview-track"><span style="width:25%"></span></div><strong>25%</strong></div><div class="preview-row"><span>Arm b</span><div class="preview-track"><span style="width:75%"></span></div><strong>75%</strong></div><p class="caption">Two sessions per arm. All four finalized.<br>Authored outcome: YES.</p><div class="preview-score"><span>Brier score · a / b</span><strong>0.5625 / 0.0625</strong></div><p class="caption">Actual provider cost: $0.<br>Fixed responses demonstrate the workflow.</p></figure></section>
<div class="content-layout"><aside class="sidebar"><nav aria-label="On this page"><p class="eyebrow">The complete walkthrough</p>''' + nav + '''</nav><p class="sidebar-note">Vorhersage<br><span>German for “forecast.”</span></p></aside><div class="content">''' + ''.join(s[2] for s in sections) + '''</div></div></main><footer class="site-footer"><span>Vorhersage · Expected Parrot</span><a href="single-question.html">Single-question walkthrough</a></footer><div id="copy-status" class="sr-only" role="status" aria-live="polite"></div><script id="session-trace" type="application/json">''' + json.dumps(summary['trace']).replace('<','\\u003c') + '''</script></body></html>'''
(DOCS / 'index.html').write_text(page)
with zipfile.ZipFile(DOCS / 'assets/session-tutorial.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
    for path in sorted((DOCS / 'assets/session-tutorial').glob('*.py')):
        archive.write(path, path.name)
print('Built docs/index.html and docs/assets/session-tutorial.zip from captured receipts.')
