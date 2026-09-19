"""Score the Firecrawl-assisted arm against the already sealed original targets."""
import json
from pathlib import Path
from statistics import mean

HERE=Path(__file__).resolve().parent
OLD=HERE.parent/'kalshi_repeated_20260918'
RUN=HERE/'run'
models=['astra','fable','gemini']
out=[]
for model in models:
    sealed=json.loads((RUN/model/'sealed-forecasts.json').read_text())['forecasts']
    for q in ['measles','global_heat']:
        target=json.loads((OLD/'run/revealed-targets'/f'{q}.json').read_text())['baseline']['quote']['midpoint']
        vals=[x['probability'] for x in sealed if x['question_id']==q and x['condition']=='outside_research']
        out.append({'model':model,'question':q,'target':target,'research_mean':mean(vals),'research_mae_pp':mean(abs(v-target)*100 for v in vals),'draws':vals})
print(json.dumps(out,indent=2))
(HERE/'real-research-scores.json').write_text(json.dumps(out,indent=2)+'\n')
