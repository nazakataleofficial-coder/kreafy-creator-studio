# Test and Quality Strategy — proposal

## Testing levels
Unit tests for parsers/timing, integration tests for engines and persisted jobs, end-to-end tests using actual audio/video/images, visual screenshot regression, security tests, performance tests on baseline Windows hardware, migration/update/rollback tests.

## Golden fixtures (to source or create legally)
T01 30s English narration; T02 English/Urdu mixed audio; T03 5min talking head; T04 2-minute documentary script; T05 20 scene images with VO; T06 noisy audio; T07 corrupt media; T08 interrupted render; T09 old project after update.

## Quality gates
Check ffprobe metadata/playability, duration, audio presence, captions safe areas/timing, visual crop, black frames, motion steadiness, correct asset placement and scene identity. Character/hand/visual anomalies may require human approval.

## Evidence
Record test command, fixture hash, expected/actual outputs, screenshots, errors, performance, branch and commit. AI claim alone is not completion. No unlicensed or private media fixtures in public repos.
