# Five paired traces

Exactly five questions, two conditions each; one initial attempt per condition.

No answer judging or qualitative scoring was run. Completion is not correctness.

Rate limiting affected this experiment. Treat latency and failed-run differences as confounded by API availability; this batch does not establish a method-level performance advantage. There was one initial attempt per condition, with four concurrent runs at most.

Full sanitized artifacts are in each pair archive. Extract it to inspect raw events, prompts, tool responses, API usage, and first-move audit JSON. Readable transcripts are also linked directly.

| Question | Gambit | Baseline | Complete pair artifacts |
|---|---|---|---|
| 770 | [failed](770/questions_gambit-transcript.md) ([answer](770/questions_gambit-answer.md)) | [completed](770/pi_serini-transcript.md) ([answer](770/pi_serini-answer.md)) | [archive](770/traces.tar.gz) |
| 781 | [completed](781/questions_gambit-transcript.md) ([answer](781/questions_gambit-answer.md)) | [completed](781/pi_serini-transcript.md) ([answer](781/pi_serini-answer.md)) | [archive](781/traces.tar.gz) |
| 788 | [completed](788/questions_gambit-transcript.md) ([answer](788/questions_gambit-answer.md)) | [completed](788/pi_serini-transcript.md) ([answer](788/pi_serini-answer.md)) | [archive](788/traces.tar.gz) |
| 792 | [completed](792/questions_gambit-transcript.md) ([answer](792/questions_gambit-answer.md)) | [completed](792/pi_serini-transcript.md) ([answer](792/pi_serini-answer.md)) | [archive](792/traces.tar.gz) |
| 244 | [completed](244/questions_gambit-transcript.md) ([answer](244/questions_gambit-answer.md)) | [failed](244/pi_serini-transcript.md) ([answer](244/pi_serini-answer.md)) | [archive](244/traces.tar.gz) |

Gambit–770 and baseline–244 failed after repeated API token-rate-limit errors and produced no completed answers. Their partial traces are preserved; no replacement attempts were run. See validation.json for all final statuses and API errors, including errors recovered within completed runs.

Public copies redact credentials, API organization identifiers, and the local workspace path. Local raw artifacts remain unchanged. Obsolete answer.json files are omitted: they were intermediate full-result exports rather than final-answer files. Use answer.md.

Each archive includes per-run prompts/configuration and logs. The manifests and configuration below describe the entire experiment. Agent-call retries within the original runtime, including recovered API errors, remain visible in the traces.

- [Protocol validation](validation.json)
- [Run summary](summary.json)
- [Configuration](configuration.json)
- [Manifest](manifest.json)
- [Attribution and license](NOTICE.md)
