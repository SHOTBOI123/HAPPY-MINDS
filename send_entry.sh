#!/bin/bash
curl -sS http://127.0.0.1:8000/analyze \
  -H 'Content-Type: application/json' \
  -d '{"text":"I hate dogs"}' \
  | python -m json.tool > out/response-$(date +%Y%m%d-%H%M%S).json
