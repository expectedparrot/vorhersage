#!/usr/bin/env python3
"""Register three correlated NFL questions and leave them ready for live research."""

import argparse
import json
from pathlib import Path

from vorhersage.common import now
from vorhersage.workflow import Workflow


def seed(project):
    w = Workflow(project)
    w.store.init("Initial prospective NFL research queue")
    definitions = [
        ("ne_playoffs_2026", "Will New England qualify for the 2026-season NFL playoffs?",
         "The NFL's official playoff field for the 2026 season includes the New England Patriots.",
         "The NFL finalizes the 2026-season playoff field without the New England Patriots."),
        ("ne_afc_2026", "Will New England be the AFC champion for the 2026 NFL season?",
         "The NFL designates the New England Patriots as AFC champion for the 2026 season.",
         "The NFL designates another team as AFC champion for the 2026 season."),
        ("ne_super_bowl_lxi", "Will New England be the official winner of Super Bowl LXI?",
         "The NFL's official final result names the New England Patriots as winner of Super Bowl LXI.",
         "The NFL's official final result names another team as winner of Super Bowl LXI."),
    ]
    queue = []
    for id, text, yes, no in definitions:
        q = {"id": id, "text": text, "yes": yes + " Follow the named season/event if rescheduled within the deadline.",
             "no": no, "void": "No qualifying official result is established by March 31, 2027, including cancellation or unresolved dispute.",
             "event_deadline": "2027-03-31T23:59:59Z", "resolve_after": "2027-04-01T00:00:00Z",
             "resolution_source": "https://www.nfl.com/", "event_group": "nfl_2026", "domain": "sports",
             "profile": "team_championship", "kind": "real"}
        w.question(q)
        r = w.start({"question_id": id, "forecaster": "agent:vorhersage-live", "method": "researched judgment v1",
                     "mode": "prospective", "information_as_of": now(), "max_searches": 12, "max_extra_tasks": 2})
        queue.append({"question": q, **r})
    output = {"queue": queue, "forecast_count": 0,
              "notes": ["No probabilities issued; each run awaits research and judgment.",
                        "These are related events in one NFL season, not three independent validation cases.",
                        "Prospective live cutoffs advance on accepted submissions; the original start cutoff is also retained.",
                        "The final deadline is a backstop; record official outcomes promptly when known."]}
    Path(project, "research_queue.json").write_text(json.dumps(output, indent=2) + "\n")
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path)
    print(json.dumps(seed(parser.parse_args().project), indent=2))
