#!/usr/bin/env bash
# Rebuild the scorecard from ira-kenya-data (set IRA_DATA_DIR if it is not next to this repo).
set -e
python src/scorecard/metrics.py
python src/scorecard/score.py
python src/scorecard/backtest.py
