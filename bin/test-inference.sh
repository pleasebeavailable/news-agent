#!/usr/bin/env bash
curl -s -X POST https://inference.local/v1/chat/completions -H "Content-Type: application/json" -d@/tmp/req.json
